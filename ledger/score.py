"""Score one prediction against the session's bars. R is measured on the stock, before option costs.

Rules (scorer v1):
- Trigger: first bar CLOSE beyond the level.
- Fill: a later bar touches the entry (call: low <= entry; put: high >= entry) and closes back on the
  trade side of the level ("then a dip holds it" / "then a bounce fails under it"), outside the card's
  no-entry windows (stored in New York time). A close through the stop before any valid retest kills the setup.
- Stop: a bar CLOSE through the stop. Target: the bar's high/low reaches it.
- Same bar reaches T1 and closes through the stop: flagged, scored as a stop (conservative).
- Exit policies, all scored:
    card       T1 (exit at T1) or stop (exit at that close) or the session close.
    five_min   card rules, but at the close of the bar that ends >= 5 min after the fill bar, exit
               if the trade is not in profit ("out after 5 minutes if it isn't working").
    hold_t2    T2 or stop or the session close.
"""
from __future__ import annotations

from datetime import timedelta

from .common import NY, canonical_hash, parse_t

SCHEMA = "outcome/1"
SCORER_VERSION = "1.0"


def _blocked(t, windows) -> bool:
    s = t.astimezone(NY)
    hm = s.strftime("%H:%M")
    return any(a <= hm < b for a, b in windows)


def _walk(p, B, fi, policy):
    """Return (exit_px, exit_idx, result, t1_idx, t2_idx, conflict, mfe, mae) for one policy."""
    sg = 1 if p["side"] == "call" else -1
    entry, stop, t1, t2 = p["entry"], p["stop"], p["t1"], p["t2"]
    risk = abs(entry - stop)
    T = [parse_t(x) for x in B["time"]]
    n = len(T)
    check_i = None
    if policy == "five_min":
        step = timedelta(seconds=B["bar_seconds"])
        check_i = next((i for i in range(fi, n) if T[i] + step - T[fi] >= timedelta(minutes=5)), None)
    target = t2 if policy == "hold_t2" else t1
    mfe = mae = 0.0
    t1_i = t2_i = None
    conflict = False
    for i in range(fi, n):
        hi, lo, c = B["high"][i], B["low"][i], B["close"][i]
        fav = sg * ((hi if sg > 0 else lo) - entry)
        adv = sg * ((lo if sg > 0 else hi) - entry)
        stop_hit = i > fi and sg * (stop - c) > 0
        tgt_hit = target is not None and fav >= abs(target - entry)
        if t1_i is None and fav >= abs(t1 - entry):
            t1_i = i
        if t2_i is None and t2 is not None and fav >= abs(t2 - entry):
            t2_i = i
        mfe, mae = max(mfe, fav), min(mae, adv)
        if tgt_hit and stop_hit:
            conflict = True
            return c, i, "stopped", t1_i, t2_i, conflict, mfe / risk, mae / risk
        if tgt_hit:
            return target, i, "target2" if policy == "hold_t2" else "target1", t1_i, t2_i, conflict, mfe / risk, mae / risk
        if stop_hit:
            return c, i, "stopped", t1_i, t2_i, conflict, mfe / risk, mae / risk
        if i == check_i and sg * (c - entry) <= 0:
            return c, i, "time_exit", t1_i, t2_i, conflict, mfe / risk, mae / risk
    return B["close"][-1], n - 1, "session_close", t1_i, t2_i, conflict, mfe / risk, mae / risk


def score(p: dict, B: dict, *, bars_sha256: str, recorded_at: str) -> dict:
    sg = 1 if p["side"] == "call" else -1
    lvl, entry, stop = p["level"], p["entry"], p["stop"]
    risk = abs(entry - stop)
    windows = p.get("no_entry_windows_et", [])
    T = [parse_t(x) for x in B["time"]]
    C, H, L = B["close"], B["high"], B["low"]
    n = len(T)
    o = {
        "schema": SCHEMA, "id": p["id"], "session": p["session"], "symbol": p["symbol"], "side": p["side"],
        "prediction_sha256": p["sha256"], "scorer_version": SCORER_VERSION, "recorded_at": recorded_at,
        "bars": {"source": B["source"], "bar_seconds": B["bar_seconds"], "rth_only": B["rth_only"],
                 "sha256": bars_sha256, "approximate": B["bar_seconds"] != 120},
        "day": {"open": B["open"][0], "high": max(H), "low": min(L), "close": C[-1]},
        "triggered": False, "trigger_time": None, "filled": False, "fill_time": None,
        "retests_in_blocked_window": 0, "result": "no_trigger",
    }
    o["bias_correct"] = _bias_correct(p, o["day"])
    ti = next((i for i in range(n) if sg * (C[i] - lvl) > 0), None)
    if ti is None:
        return _finish(o)
    o.update(triggered=True, trigger_time=B["time"][ti], result="no_fill")
    fi = None
    for i in range(ti + 1, n):
        touched = L[i] <= entry if sg > 0 else H[i] >= entry
        if touched and sg * (C[i] - lvl) >= 0:
            if _blocked(T[i], windows):
                o["retests_in_blocked_window"] += 1
                continue
            fi = i
            break
        if sg * (stop - C[i]) > 0:
            o["result"] = "failed_before_retest"
            break
    if fi is None:
        return _finish(o)
    o.update(filled=True, fill_time=B["time"][fi])
    pol = {}
    for name in ("card", "five_min", "hold_t2"):
        px, xi, res, t1_i, t2_i, conflict, mfe, mae = _walk(p, B, fi, name)
        pol[name] = {"result": res, "exit": round(px, 2), "exit_time": B["time"][xi],
                     "r": round(sg * (px - entry) / risk, 2), "same_bar_conflict": conflict}
        if name == "card":
            o.update(result=res, mfe_r=round(mfe, 2), mae_r=round(mae, 2),
                     t1_hit=t1_i is not None, t1_time=B["time"][t1_i] if t1_i is not None else None,
                     minutes_to_t1=int((T[t1_i] - T[fi]).total_seconds() // 60) if t1_i is not None else None)
        if name == "hold_t2":
            o.update(t2_hit=t2_i is not None, mfe_session_r=round(mfe, 2), mae_session_r=round(mae, 2))
    o["policies"] = pol
    o["r"] = pol["card"]["r"]
    return _finish(o)


def _bias_correct(p, day) -> bool:
    """support: the floor held all day (low stayed above it); breakout: the session closed above the ceiling."""
    if p["bias"] == "support":
        return day["low"] >= p["floor"]
    return day["close"] > p["ceiling"]


def _finish(o):
    o.setdefault("policies", None)
    o.setdefault("r", None)
    o["sha256"] = canonical_hash(o)
    return o
