"""How far off is a setup scored on 30- or 60-minute bars? Measured on the published cards, which also have fine bars.

python tools/tier_check.py --m30 DIR_OF_<contract_id>.json   ->  reports/tier_check.json

Each published setup is scored three ways: on its stored fine bars (2- or 5-minute), on IBKR 30-minute bars of
the same day, and on 60-minute bars built from those (09:30-10:00 alone, then on the hour, as IBKR's hourly
bars are). The gaps between them are the error bar on the rebuilt 30- and 60-minute history.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledger import bars as barsmod  # noqa: E402
from ledger import score  # noqa: E402
from ledger.common import NY, ROOT, parse_t, read_jsonl  # noqa: E402


def hourly(day: dict) -> dict:
    out = {k: day[k] for k in ("symbol", "source", "kind", "rth_only", "price") if k in day} | {
        "bar_seconds": 3600, "time": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    key = None
    for i, t in enumerate(day["time"]):
        ny = parse_t(t).astimezone(NY)
        k = "09:30" if (ny.hour, ny.minute) == (9, 30) else f"{ny.hour:02d}:00"
        if k != key:
            key = k
            out["time"].append(t)
            for f in ("open", "high", "low", "close", "volume"):
                out[f].append(day[f][i])
        else:
            out["high"][-1] = max(out["high"][-1], day["high"][i])
            out["low"][-1] = min(out["low"][-1], day["low"][i])
            out["close"][-1] = day["close"][i]
            out["volume"][-1] += day["volume"][i]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m30", required=True)
    a = ap.parse_args(argv)
    ids = json.loads((ROOT / "ledger" / "contracts.json").read_text())
    m30 = {}
    for sym, cid in ids.items():
        f = Path(a.m30) / f"{cid}.json"
        if f.exists():
            m30[sym] = barsmod.split_ibkr(json.loads(f.read_text()), symbol=sym)
    rows = []
    for f in sorted((ROOT / "predictions").rglob("*.jsonl")):
        for p in read_jsonl(f):
            if p.get("card_source"):
                continue
            fine, h = barsmod.load_day(p["session"], p["symbol"])
            d30 = m30.get(p["symbol"], {}).get(p["session"])
            if fine is None or d30 is None:
                continue
            res = {"id": p["id"], "fine_bar_seconds": fine["bar_seconds"]}
            for label, B in (("fine", fine), ("30min", d30), ("60min", hourly(d30))):
                o = score.score(p, B, bars_sha256="-", recorded_at="-")
                res[label] = {"result": o["result"], "filled": o["filled"], "r": o["r"],
                              "r_hold_t2": o["policies"]["hold_t2"]["r"] if o["policies"] else None}
            rows.append(res)

    def agg(label):
        same = sum(1 for r in rows if r[label]["result"] == r["fine"]["result"])
        both = [r for r in rows if r[label]["r"] is not None and r["fine"]["r"] is not None]
        only_c = sum(1 for r in rows if r[label]["filled"] and not r["fine"]["filled"])
        only_f = sum(1 for r in rows if r["fine"]["filled"] and not r[label]["filled"])
        rc = [r[label]["r"] for r in rows if r[label]["r"] is not None]
        rf = [r["fine"]["r"] for r in rows if r["fine"]["r"] is not None]
        stops = lambda k: sum(1 for r in rows if r[k]["result"] == "stopped")
        return {"setups": len(rows), "same_result": same, "stopped_fine": stops("fine"), "stopped_coarse": stops(label),
                "filled_fine": len(rf), "filled_coarse": len(rc),
                "filled_only_on_coarse": only_c, "filled_only_on_fine": only_f,
                "avg_r_fine": round(statistics.mean(rf), 3) if rf else None,
                "avg_r_coarse": round(statistics.mean(rc), 3) if rc else None,
                "avg_r_gap_when_both_filled": round(statistics.mean(r[label]["r"] - r["fine"]["r"] for r in both), 3) if both else None,
                "both_filled": len(both)}
    out = {"what": "published setups scored on fine bars vs 30- and 60-minute bars of the same day",
           "sessions": sorted({r["id"][:10] for r in rows}), "30min": agg("30min"), "60min": agg("60min"), "setups": rows}
    (ROOT / "reports" / "tier_check.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("sessions", "30min", "60min")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
