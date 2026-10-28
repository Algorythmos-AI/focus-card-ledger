"""Pull 1-minute regular-hours bars from the Webull AU OpenAPI (read only) and store them as 2-minute bars.

python tools/webull_bars.py --from 2026-05-01 --to 2026-10-28 --out DIR [--names SPY,QQQ]

Needs WEBULL_APP_KEY / WEBULL_APP_SECRET in the environment and the free "Nasdaq Basic - Non Display" OpenAPI
quote permission. Webull keeps minute bars for 180 days. Writes DIR/<SYMBOL>/<session>.json in the ledger's
bar format (source "Webull", bar_seconds 120): two 1-minute bars per 2-minute bar, aligned to 09:30 ET.
No orders: only the market-data endpoint is called.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ledger.common import NY  # noqa: E402

NAMES = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "PLTR", "AVGO", "AMD"]
ETF = {"SPY", "QQQ"}


def client():
    os.environ.setdefault("WEBULL_OPENAPI_TOKEN_DIR", os.path.expanduser("~/.webull-token"))
    from webull.core.client import ApiClient
    from webull.data.data_client import DataClient
    api = ApiClient(os.environ["WEBULL_APP_KEY"], os.environ["WEBULL_APP_SECRET"], "au")
    api.set_stream_logger(stream=sys.stderr, log_level=logging.CRITICAL)
    return DataClient(api)


def ms(t: datetime) -> str:
    return str(int(t.timestamp() * 1000))


def fetch(dc, sym: str, start: datetime, end: datetime) -> list[dict]:
    for attempt in range(4):
        try:
            r = dc.market_data.get_history_bar(sym, "US_ETF" if sym in ETF else "US_STOCK", "M1", count="1200",
                                               start_time=ms(start), end_time=ms(end))
            return [b for x in r.json().get("result", []) for b in x.get("result", [])]
        except Exception as e:  # rate limit or a dropped connection: back off and retry
            time.sleep(2 ** attempt * 2)
            err = e
    raise RuntimeError(f"{sym} {start:%Y-%m-%d}: {err}")


def to_days(sym: str, rows: list[dict]) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for b in sorted(rows, key=lambda b: b["time"]):
        if b.get("trading_session") != "RTH":
            continue
        t = datetime.fromisoformat(b["time"].replace("+0000", "+00:00"))
        ny = t.astimezone(NY)
        m = ny.hour * 60 + ny.minute
        if not (570 <= m < 960):
            continue
        slot = t - timedelta(minutes=(m - 570) % 2)
        d = days.setdefault(ny.date().isoformat(), {"symbol": sym, "source": "Webull", "kind": "STK", "bar_seconds": 120,
                                                     "rth_only": True, "price": "Last (Nasdaq Basic, 1-min aggregated)",
                                                     "time": [], "open": [], "high": [], "low": [], "close": [], "volume": []})
        key = slot.strftime("%Y-%m-%dT%H:%M:%SZ")
        o, h, l, c, v = (float(b[k]) for k in ("open", "high", "low", "close", "volume"))
        if d["time"] and d["time"][-1] == key:
            d["high"][-1] = max(d["high"][-1], h)
            d["low"][-1] = min(d["low"][-1], l)
            d["close"][-1] = c
            d["volume"][-1] += v
        else:
            d["time"].append(key)
            for f, x in zip(("open", "high", "low", "close", "volume"), (o, h, l, c, v)):
                d[f].append(x)
    return days


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", default=",".join(NAMES))
    a = ap.parse_args(argv)
    dc = client()
    t0 = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    t_end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(days=1)
    for sym in a.names.split(","):
        out = Path(a.out) / sym
        out.mkdir(parents=True, exist_ok=True)
        t, n = t0, 0
        while t < t_end:
            if t.weekday() < 5:
                # One session per call: with pre- and post-market a day is ~960 bars and a call returns 1,200 at most,
                # so a wider window silently drops the start of its first day.
                for d, day in to_days(sym, fetch(dc, sym, t + timedelta(hours=13), t + timedelta(hours=21))).items():
                    (out / f"{d}.json").write_text(json.dumps(day, separators=(",", ":")))
                    n += 1
                time.sleep(1.05)  # 60 requests a minute
            t += timedelta(days=1)
        print(sym, n, "sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
