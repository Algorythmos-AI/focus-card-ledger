"""Scorecard (approach A) and analytics (approach B) over every prediction and outcome in the ledger.

Every rate carries a 95% Wilson interval. Slices are fixed here, in advance, so we don't go hunting for
lucky ones. Setups from the same day move together, so treat per-slice intervals as optimistic.
"""
from __future__ import annotations

import csv
import io
import statistics
from collections import defaultdict

from .common import ROOT, read_jsonl, wilson

POLICIES = ("card", "five_min", "hold_t2")
SLICES = ("symbol", "side", "bias", "rank", "confidence", "level_type", "gap", "backfilled", "bar_size")


def load() -> list[dict]:
    rows = []
    preds = {p["id"]: p for f in sorted((ROOT / "predictions").rglob("*.jsonl")) for p in read_jsonl(f)}
    outs = {o["id"]: o for f in sorted((ROOT / "outcomes").rglob("*.jsonl")) for o in read_jsonl(f)}
    opts = {o["id"]: o for f in sorted((ROOT / "options").rglob("*.jsonl")) for o in read_jsonl(f)}
    for pid, p in preds.items():
        o = outs.get(pid)
        if o is None:
            continue
        rows.append(flatten(p, o, opts.get(pid)))
    rows.sort(key=lambda r: (r["session"], r["rank"], r["side"]))
    return rows


def _gap(p):
    pre = p.get("premarket")
    if not pre:
        return "unknown"
    return {"above_resistance": "gap_over_ceiling", "below_support": "gap_under_floor"}.get(pre["where"], "inside")


def flatten(p, o, opt=None) -> dict:
    r = {k: p[k] for k in ("id", "session", "symbol", "side", "rank", "bias", "confidence", "card_score",
                           "level", "entry", "stop", "t1", "t2", "backfilled")}
    r["level_type"] = p["level_source"].split("/")[0]
    r["gap"] = _gap(p)
    r["bar_size"] = f'{o["bars"]["bar_seconds"] // 60}min'
    for k in ("triggered", "filled", "result", "fill_time", "t1_hit", "t2_hit", "mfe_r", "mae_r",
              "minutes_to_t1", "bias_correct", "trigger_time"):
        r[k] = o.get(k)
    for pol in POLICIES:
        r[f"r_{pol}"] = o["policies"][pol]["r"] if o.get("policies") else None
    if opt and opt.get("policies"):
        r["option_entry"] = opt["contract"]["entry_premium"]
        for pol in POLICIES:
            r[f"opt_usd_{pol}"] = opt["policies"][pol]["pnl_usd"]
    return r


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    trig = [r for r in rows if r["triggered"]]
    fill = [r for r in rows if r["filled"]]
    wins = [r for r in fill if r["t1_hit"] and r["result"] == "target1"]
    stops = [r for r in fill if r["result"] == "stopped"]
    s = {"setups": n, "triggered": len(trig), "filled": len(fill)}
    s["trigger_rate"] = _rate(len(trig), n)
    s["fill_rate_of_triggered"] = _rate(len(fill), len(trig))
    s["win_rate_t1_before_stop"] = _rate(len(wins), len(fill))
    s["stop_rate"] = _rate(len(stops), len(fill))
    s["t2_hit_rate"] = _rate(sum(1 for r in fill if r["t2_hit"]), len(fill))
    for pol in POLICIES:
        rs = [r[f"r_{pol}"] for r in fill if r[f"r_{pol}"] is not None]
        gw, gl = sum(x for x in rs if x > 0), -sum(x for x in rs if x < 0)
        s[f"{pol}_expectancy_r"] = round(statistics.mean(rs), 3) if rs else None
        s[f"{pol}_total_r"] = round(sum(rs), 2)
        s[f"{pol}_profit_factor"] = round(gw / gl, 2) if gl else None
        us = [r.get(f"opt_usd_{pol}") for r in fill if r.get(f"opt_usd_{pol}") is not None]
        s[f"{pol}_option_usd_total"] = round(sum(us), 2) if us else None
        s[f"{pol}_option_trades"] = len(us)
    s["avg_mfe_r"] = _mean([r["mfe_r"] for r in fill])
    s["avg_mae_r"] = _mean([r["mae_r"] for r in fill])
    m = [r["minutes_to_t1"] for r in fill if r["minutes_to_t1"] is not None]
    s["median_minutes_to_t1"] = statistics.median(m) if m else None
    bias = {}
    for r in rows:
        if r["bias_correct"] is not None:
            bias[(r["session"], r["symbol"])] = r["bias_correct"]
    s["bias_hit_rate"] = _rate(sum(bias.values()), len(bias))
    return s


def _rate(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "ci95": [lo, hi]}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def spearman(xs, ys):
    """Rank correlation (information coefficient) between a pre-open score and the realised R."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2
            i = j + 1
        return rk
    a, b = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = statistics.mean(a), statistics.mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return round(cov / (va * vb) ** 0.5, 3) if va and vb else None


def scorecard(rows: list[dict], rolling_sessions: int = 20) -> dict:
    sessions = sorted({r["session"] for r in rows})
    card = {"as_of_session": sessions[-1] if sessions else None, "sessions": len(sessions),
            "all": summarize(rows), "live_only": summarize([r for r in rows if not r["backfilled"]])}
    recent = set(sessions[-rolling_sessions:])
    card[f"rolling_{rolling_sessions}"] = summarize([r for r in rows if r["session"] in recent])
    card["by"] = {}
    for key in SLICES:
        groups = defaultdict(list)
        for r in rows:
            groups[str(r[key])].append(r)
        card["by"][key] = {g: summarize(v) for g, v in sorted(groups.items())}
    filled = [r for r in rows if r["filled"]]
    card["calibration"] = {
        "ic_card_score_vs_r": spearman([r["card_score"] for r in filled], [r["r_card"] for r in filled]),
        "ic_rank_vs_r": spearman([-r["rank"] for r in filled], [r["r_card"] for r in filled]),
        "win_rate_by_confidence": {c: summarize([r for r in rows if r["confidence"] == c])["win_rate_t1_before_stop"]
                                   for c in ("high", "medium", "low")},
    }
    return card


def to_csv(rows: list[dict]) -> str:
    cols = sorted({k for r in rows for k in r})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def export_parquet(rows: list[dict], path) -> bool:
    """Optional B layer: one Parquet table for DuckDB/pandas. Rebuilt from the JSONL, never edited."""
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    import json
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(rows, f)
    duckdb.sql(f"COPY (SELECT * FROM read_json_auto('{f.name}')) TO '{path}' (FORMAT PARQUET)")
    return True
