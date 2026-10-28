"""Store intraday bars per session and symbol: bars/<yyyy>/<session>/<SYMBOL>.json (regular hours only).

Input is an IBKR get_price_history response (it may span several sessions). Bars are split by New York
date, so each session's file is complete on its own and its sha256 can be quoted by the outcome.
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import NY, ROOT, file_hash, parse_t

FIELDS = ("open", "high", "low", "close", "volume")


def split_ibkr(resp: dict, *, symbol: str, source: str = "IBKR", kind: str = "STK") -> dict[str, dict]:
    step = int(resp["chart_step"])
    days: dict[str, dict] = {}
    for i, t in enumerate(resp["time"]):
        ny = parse_t(t).astimezone(NY)
        hm = ny.hour * 60 + ny.minute
        if not (570 <= hm < 960):  # 09:30-16:00 ET
            continue
        d = days.setdefault(ny.date().isoformat(), {
            "symbol": symbol, "source": source, "kind": kind, "bar_seconds": step, "rth_only": True,
            "price": resp.get("source", "Last"), "time": [], **{f: [] for f in FIELDS}})
        d["time"].append(t)
        for f in FIELDS:
            d[f].append(resp[f][i])
    return days


def bars_path(session: str, name: str) -> Path:
    return ROOT / "bars" / session[:4] / session / f"{name}.json"


def save_day(session: str, name: str, day: dict, *, overwrite: bool = False) -> Path:
    p = bars_path(session, name)
    if p.exists() and not overwrite:
        old = json.loads(p.read_text())
        rank = lambda d: (is_complete(d) and _starts_at_open(d), -d["bar_seconds"], len(d["time"]))
        if rank(old) >= rank(day):
            return p  # keep the complete, finer copy already stored
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(day, separators=(",", ":")))
    return p


def load_day(session: str, name: str) -> tuple[dict, str] | tuple[None, None]:
    p = bars_path(session, name)
    if not p.exists():
        return None, None
    return json.loads(p.read_text()), file_hash(p)


def _starts_at_open(day: dict) -> bool:
    first = parse_t(day["time"][0]).astimezone(NY)
    return first.hour == 9 and first.minute == 30


def is_complete(day: dict) -> bool:
    """A full session has bars to 15:5x ET (half days end 12:5x ET)."""
    last = parse_t(day["time"][-1]).astimezone(NY)
    return last.hour * 60 + last.minute + day["bar_seconds"] // 60 >= 780
