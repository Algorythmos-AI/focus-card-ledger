"""Approach C: what each filled setup would have done in the option Sam would buy.

Contract rule (from the card's size line): the nearest out-of-the-money strike, moving further out until
the premium at the fill bar is $2.00 or less, so the -25% option stop risks at most $50. Expiry: the
nearest one on or after the session (0DTE when it exists).

Prices are the option's 2-minute LAST-trade bars from IBKR (delayed 15 min, pulled after the close).
Entry = the option bar close at the stock fill bar. Exit = the earlier of the -25% option stop
(first bar whose low reaches 75% of entry, filled at that 75%) and the stock policy's exit bar close.
These are estimates: no bid/ask spread, no slippage, no fees.
"""
from __future__ import annotations

from .common import canonical_hash, parse_t

SCHEMA = "option_outcome/1"
MAX_PREMIUM = 2.00
OPTION_STOP = 0.25


def _idx(B: dict, t: str) -> int | None:
    want = parse_t(t)
    return next((i for i, x in enumerate(B["time"]) if parse_t(x) == want), None)


def choose(side: str, stock_entry: float, fill_time: str, chain: list[tuple[float, dict]]) -> tuple[float, dict, float] | None:
    """chain: [(strike, option_bars)], any order. Returns (strike, bars, premium) or None."""
    otm = sorted((s for s in chain if (s[0] > stock_entry if side == "call" else s[0] < stock_entry)),
                 key=lambda s: abs(s[0] - stock_entry))
    for strike, bars in otm:
        i = _idx(bars, fill_time)
        if i is not None and bars["close"][i] <= MAX_PREMIUM:
            return strike, bars, bars["close"][i]
    return None


def score_option(o: dict, *, strike: float | None, expiry: str | None, description: str | None,
                 bars: dict | None, bars_sha256: str | None, recorded_at: str, note: str | None = None) -> dict:
    rec = {"schema": SCHEMA, "id": o["id"], "session": o["session"], "symbol": o["symbol"], "side": o["side"],
           "outcome_sha256": o["sha256"], "recorded_at": recorded_at, "contract": None, "policies": None,
           "note": note}
    if bars is None or not o.get("filled"):
        rec["note"] = note or ("not filled" if not o.get("filled") else "no option under $2.00")
        rec["sha256"] = canonical_hash(rec)
        return rec
    fi = _idx(bars, o["fill_time"])
    entry = bars["close"][fi]
    rec["contract"] = {"strike": strike, "right": "C" if o["side"] == "call" else "P", "expiry": expiry,
                       "description": description, "entry_premium": entry, "max_risk_usd": round(entry * 100 * OPTION_STOP, 2),
                       "bars": {"source": bars.get("source", "IBKR"), "bar_seconds": bars["bar_seconds"],
                                "price": "last trade", "sha256": bars_sha256}}
    stop_px = round(entry * (1 - OPTION_STOP), 2)
    pols = {}
    for name, pol in o["policies"].items():
        xi = _idx(bars, pol["exit_time"])
        exit_px, why, xt = None, pol["result"], pol["exit_time"]
        for i in range(fi + 1, (xi if xi is not None else len(bars["time"]) - 1) + 1):
            if bars["low"][i] <= stop_px:
                exit_px, why, xt = stop_px, "option_stop_25pct", bars["time"][i]
                break
        if exit_px is None:
            exit_px = bars["close"][xi] if xi is not None else bars["close"][-1]
        pols[name] = {"exit_premium": exit_px, "exit_time": xt, "reason": why,
                      "pnl_usd": round((exit_px - entry) * 100, 2), "return_pct": round((exit_px / entry - 1) * 100, 1)}
    rec["policies"] = pols
    rec["sha256"] = canonical_hash(rec)
    return rec
