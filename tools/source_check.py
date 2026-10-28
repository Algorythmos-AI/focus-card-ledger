"""Do Webull bars score the same as IBKR bars? Run on the published days that have IBKR 2-minute bars.

python tools/source_check.py --webull DIR   ->  reports/source_check.json
DIR is tools/webull_bars.py output (DIR/<SYMBOL>/<session>.json).
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
from ledger.common import ROOT, read_jsonl  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webull", required=True)
    a = ap.parse_args(argv)
    rows, diffs = [], []
    for f in sorted((ROOT / "predictions").rglob("*.jsonl")):
        for p in read_jsonl(f):
            if p.get("card_source"):
                continue
            B, _ = barsmod.load_day(p["session"], p["symbol"])
            wf = Path(a.webull) / p["symbol"] / f"{p['session']}.json"
            if B is None or B["source"] != "IBKR" or B["bar_seconds"] != 120 or not wf.exists():
                continue
            W = json.loads(wf.read_text())
            ib = dict(zip(B["time"], B["close"]))
            diffs += [abs(c - ib[t]) / ib[t] * 1e4 for t, c in zip(W["time"], W["close"]) if t in ib]
            x = score.score(p, B, bars_sha256="-", recorded_at="-")
            y = score.score(p, W, bars_sha256="-", recorded_at="-")
            rows.append({"id": p["id"], "ibkr": [x["result"], x["r"]], "webull": [y["result"], y["r"]]})
    diffs.sort()
    out = {"what": "published setups with IBKR 2-min bars, rescored on Webull 1-min bars aggregated to 2-min",
           "setups": len(rows), "same_result": sum(r["ibkr"][0] == r["webull"][0] for r in rows),
           "same_r": sum(r["ibkr"][1] == r["webull"][1] for r in rows),
           "close_diff_bps": {"bars": len(diffs), "median": round(statistics.median(diffs), 2),
                              "p95": round(diffs[int(0.95 * len(diffs))], 2), "max": round(diffs[-1], 2)},
           "setups_detail": rows}
    (ROOT / "reports" / "source_check.json").write_text(json.dumps(out, indent=1) + "\n")
    print({k: out[k] for k in ("setups", "same_result", "same_r", "close_diff_bps")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
