"""The day's ledger as one edition for Sam's dashboard (lab.algorythmos.com, the Options page and Card record).

python -m ledger dashboard --session D [--out FILE] [--send]

The edition holds what the card said, each name's 2-minute closes, every side's result in R and on one option
contract, and the running record (every published day, the bar-size tiers and the rebuilt 2-minute history).
Numbers, codes and dates only: the dashboard's schema (dashboard/src/lib/ledger.schema.json in
trading-lab-research) refuses free text.

--send signs it with the radar's ingest key, as the radar push does. Secrets come from the environment only and
are never printed: RADAR_INGEST_SECRET, VERCEL_AUTOMATION_BYPASS_SECRET, and DASHBOARD_INGEST_URL (optional).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

from . import metrics
from .common import NY, ROOT, day_path, parse_t, read_jsonl, wilson

SCHEMA = "stocksdelta/ledger"
DEFAULT_URL = "https://lab.algorythmos.com/api/ingest"
TIER_KEYS = ("published", "rebuilt_2min", "rebuilt_60min")
DISTANCES = ("<0.5 ATR", "0.5-1 ATR", ">1 ATR")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")


def _z(t: str | None) -> str | None:
    return parse_t(t).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "lo": lo, "hi": hi}


def _bars(session: str, symbol: str) -> dict | None:
    f = ROOT / "bars" / session[:4] / session / f"{symbol}.json"
    if not f.exists():
        return None
    b = json.loads(f.read_text())
    out = {"bar_seconds": b["bar_seconds"], "source": b.get("source", "IBKR"), "t": [], "close": [], "high": [], "low": []}
    for i, t in enumerate(b["time"]):
        ny = parse_t(t).astimezone(NY)
        m = ny.hour * 60 + ny.minute - 570
        if 0 <= m <= 390:
            out["t"].append(m)
            for k in ("close", "high", "low"):
                out[k].append(b[k][i])
    return out if out["t"] else None


def _option(x: dict | None) -> dict | None:
    if not x or not x.get("policies"):
        return None
    c, pol = x["contract"], x["policies"]["card"]
    exp = str(c["expiry"])
    return {"right": c["right"], "strike": c["strike"], "expiry": f"{exp[:4]}-{exp[4:6]}-{exp[6:8]}" if len(exp) == 8 else exp,
            "entry_premium": c["entry_premium"], "pnl_usd": pol["pnl_usd"], "return_pct": pol["return_pct"],
            "exit_time": _z(pol["exit_time"]), "reason": pol["reason"]}


def _side(p: dict, o: dict, x: dict | None) -> dict:
    pol = o.get("policies") or {}
    return {"side": p["side"], "confidence": p["confidence"], "level": p["level"], "entry": p["entry"], "stop": p["stop"],
            "t1": p["t1"], "t2": p["t2"], "result": o["result"], "triggered": bool(o.get("triggered")),
            "filled": bool(o.get("filled")), "trigger_time": _z(o.get("trigger_time")), "fill_time": _z(o.get("fill_time")),
            "exit_time": _z(pol.get("card", {}).get("exit_time")), "exit": pol.get("card", {}).get("exit"),
            "r": o.get("r") if o.get("filled") else None,
            "r_five_min": pol.get("five_min", {}).get("r") if o.get("filled") else None,
            "r_hold_t2": pol.get("hold_t2", {}).get("r") if o.get("filled") else None,
            "option": _option(x)}


def day_totals(session: str, sides: list[dict], bias: dict[str, bool | None]) -> dict:
    fills = [s for s in sides if s["filled"]]
    opts = [s["option"]["pnl_usd"] for s in fills if s["option"] and s["option"]["pnl_usd"] is not None]
    calls = [v for v in bias.values() if v is not None]
    return {"session": session, "sides": len(sides), "triggered": sum(s["triggered"] for s in sides), "filled": len(fills),
            "t1": sum(1 for s in fills if s["result"] in ("target1", "target2")),
            "stopped": sum(1 for s in fills if s["result"] == "stopped"),
            "r": round(sum(s["r"] or 0 for s in fills), 2), "r_five_min": round(sum(s["r_five_min"] or 0 for s in fills), 2),
            "option_usd": round(sum(opts), 2) if opts else None, "option_trades": len(opts),
            "bias_right": sum(1 for v in calls if v), "bias_calls": len(calls)}


def session_doc(session: str) -> tuple[list[dict], dict, str]:
    preds = read_jsonl(day_path("predictions", session))
    outs = {o["id"]: o for o in read_jsonl(day_path("outcomes", session))}
    opts = {x["id"]: x for x in read_jsonl(day_path("options", session))}
    names: dict[str, dict] = {}
    sides, bias = [], {}
    for p in sorted(preds, key=lambda p: (p["rank"], p["side"])):
        o = outs.get(p["id"])
        if o is None:
            continue
        n = names.get(p["symbol"])
        if n is None:
            n = names[p["symbol"]] = {"symbol": p["symbol"], "rank": p["rank"], "bias": p["bias"], "ceiling": p["ceiling"],
                                      "floor": p["floor"], "atr": p["atr"], "bias_correct": None,
                                      "bars": _bars(session, p["symbol"]), "sides": []}
        if o.get("bias_correct") is not None:
            n["bias_correct"] = o["bias_correct"]
        bias[p["symbol"]] = n["bias_correct"]
        s = _side(p, o, opts.get(p["id"]))
        n["sides"].append(s)
        sides.append(s)
    source = "rebuilt" if any(p.get("card_source") == "rebuilt" for p in preds) else "published"
    return list(names.values()), day_totals(session, sides, bias), source


def _tier(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    s = metrics.summarize(rows)
    bias = {(r["session"], r["symbol"]): r["bias_correct"] for r in rows if r["bias_correct"] is not None}
    sess = sorted({r["session"] for r in rows})
    w, t = s["win_rate_t1_before_stop"], s["trigger_rate"]
    return {"from": sess[0], "to": sess[-1], "sessions": len(sess), "sides": s["setups"], "filled": s["filled"],
            "avg_r": s["card_expectancy_r"], "profit_factor": s["card_profit_factor"],
            "win": _rate(w["k"], w["n"]), "bias": _rate(sum(bias.values()), len(bias)), "trigger": _rate(t["k"], t["n"])}


def _slices(rows: list[dict], key: str, order) -> list[dict]:
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    out = []
    for k in order or sorted(g):
        rs = g.get(k, [])
        if not rs:
            continue
        rr = [r["r_card"] for r in rs if r["filled"] and r["r_card"] is not None]
        out.append({"key": k, "sides": len(rs), "filled": sum(1 for r in rs if r["filled"]),
                    "avg_r": round(sum(rr) / len(rr), 3) if rr else None,
                    "trigger_rate": round(sum(1 for r in rs if r["triggered"]) / len(rs), 3)})
    return out


def record(upto: str) -> dict:
    rows = [r for r in metrics.load() if r["session"] <= upto]
    tiers = {}
    for k in TIER_KEYS:
        t = _tier([r for r in rows if metrics.TIERS[k](r)])
        if t:
            tiers[k] = t
    pub_sessions = sorted({r["session"] for r in rows if r["card_source"] == "published"})
    days = []
    for s in pub_sessions:
        names, day, _ = session_doc(s)
        days.append(day)
    two = [r for r in rows if metrics.TIERS["rebuilt_2min"](r)]
    daily = defaultdict(float)
    for r in two:
        daily[r["session"]] += r["r_card"] if r["filled"] and r["r_card"] is not None else 0.0
    out = {"days": days, "tiers": tiers}
    if two:
        out["history"] = {"daily_r": [{"session": s, "r": round(v, 2)} for s, v in sorted(daily.items())],
                          "by_symbol": _slices(two, "symbol", None), "by_distance": _slices(two, "distance", DISTANCES),
                          "by_weekday": _slices(two, "weekday", WEEKDAYS)}
    return out


def build(session: str, *, as_of: str | None = None) -> dict:
    names, day, source = session_doc(session)
    if not names:
        raise SystemExit(f"{session}: no scored setups")
    doc = {"schema": SCHEMA, "schema_version": 1, "run_id": "", "as_of": "", "session": session,
           "scorer_version": next((o.get("scorer_version") for o in read_jsonl(day_path("outcomes", session))), "1.0"),
           "card_source": source, "names": names, "day": day, "record": record(session)}
    body = json.dumps({k: v for k, v in doc.items() if k not in ("run_id", "as_of")}, sort_keys=True, separators=(",", ":"))
    doc["run_id"] = f"ledger-{session}-{hashlib.sha256(body.encode()).hexdigest()[:12]}"
    doc["as_of"] = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return doc


def accepts(url: str, bypass: str) -> int | None:
    """The newest ledger edition the site takes, from its /api/health; None when it takes none yet or can't say."""
    req = urllib.request.Request(url.rsplit("/api/", 1)[0] + "/api/health", headers={"x-vercel-protection-bypass": bypass})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return (json.loads(r.read()).get("editions") or {}).get("ledger", {}).get("accepts")
    except (urllib.error.URLError, ValueError, AttributeError):
        return None


def send(doc: dict, url: str | None = None) -> tuple[int, str]:
    """Signs and posts the edition. (2, reason) when a secret is missing or the site does not take ledger editions
    yet: nothing is sent."""
    secret, bypass = os.environ.get("RADAR_INGEST_SECRET"), os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
    missing = [n for n, v in (("RADAR_INGEST_SECRET", secret), ("VERCEL_AUTOMATION_BYPASS_SECRET", bypass)) if not v]
    if missing:
        return 2, f"not sent: {', '.join(missing)} not set"
    url = url or os.environ.get("DASHBOARD_INGEST_URL") or DEFAULT_URL
    got = accepts(url, bypass)
    if got is None or got < doc["schema_version"]:
        return 2, "not sent: the dashboard does not take ledger editions yet (Card record not released)"
    body = json.dumps(doc, separators=(",", ":")).encode()
    ts = int(time.time())
    sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "content-type": "application/json", "x-wt-timestamp": str(ts), "x-wt-signature": sig, "x-wt-key-id": "radar",
        "x-vercel-protection-bypass": bypass})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
