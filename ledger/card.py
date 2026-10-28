"""Turn a Top 4 Focus Card (options-tab/data/focus/<date>.json) into prediction records.

The card page derives entry, stop and T1 from each level; this module applies the same formula so
the ledger stores the numbers Sam saw: entry = level +/- 0.01 ATR, stop = level -/+ 0.1 ATR,
T1 = entry +/- 2R, T2 = the card's named target.
A card carrying card_source "rebuilt" (tools/rebuild_cards.py) passes that tag and its `rebuild` note on.
"""
from __future__ import annotations

from .common import canonical_hash

SCHEMA = "prediction/1"
CARD_RULE_VERSION = "focus-card/2026-10-27"
# The card says "before 00:35 or 02:30-04:00 Sydney" (written in AEDT); stored in New York time so it
# survives the US and Australian clock changes: the first 5 minutes and the 11:30-13:00 ET lull.
NO_ENTRY_WINDOWS_ET = [["09:30", "09:35"], ["11:30", "13:00"]]


def _r2(x: float) -> float:
    return round(x + 0.0, 2)


def derive_levels(item: dict, side: str) -> dict:
    atr, sg = item["atr"], 1 if side == "call" else -1
    level = item["breakout_above"] if side == "call" else item["hold_above"]
    entry = _r2(level + sg * 0.01 * atr)
    stop = _r2(level - sg * 0.1 * atr)
    t1 = _r2(entry + sg * 2 * abs(entry - stop))
    tgt = item["target_up"] if side == "call" else item["target_down"]
    lvl_src = item["resistance"]["name"] if side == "call" else item["support"]["name"]
    return dict(level=level, level_source=lvl_src, entry=entry, stop=stop, t1=t1,
                t2=tgt["price"] if tgt else None, t2_source=tgt["name"] if tgt else None)


def confidence_v1(side: str, pre: dict | None) -> str:
    """Rule fixed before any outcome is known: does the pre-market already lean to this side?"""
    if not pre:
        return "medium"
    where = pre.get("where", "")
    if (side == "call" and where == "above_resistance") or (side == "put" and where == "below_support"):
        return "high"
    if (side == "call" and where == "below_support") or (side == "put" and where == "above_resistance"):
        return "low"
    return "medium"


def predictions_from_card(card: dict, *, recorded_at: str, backfilled: bool = False) -> list[dict]:
    pre_by = {p["symbol"]: p for p in (card.get("premarket") or {}).get("items", [])}
    pre_asof = (card.get("premarket") or {}).get("as_of")
    out = []
    for it in sorted(card["items"], key=lambda x: x["rank"]):
        pre = pre_by.get(it["symbol"])
        for side in ("call", "put"):
            if it["breakout_above" if side == "call" else "hold_above"] is None:
                continue  # no level on that side (e.g. at a one-year high): the card shows no plan for it
            rec = {
                "schema": SCHEMA,
                "id": f'{card["session"]}-{it["symbol"]}-{side}',
                "session": card["session"],
                "symbol": it["symbol"],
                "side": side,
                "rank": it["rank"],
                "bias": it["bias"],
                "card_score": it.get("score"),
                "why": it.get("why"),
                **derive_levels(it, side),
                "ceiling": it["breakout_above"],
                "floor": it["hold_above"],
                "atr": it["atr"],
                "prior_close": it["close"],
                "premarket": ({"as_of": pre_asof, "price": pre["price"], "gap_pct": pre["gap_pct"],
                               "where": pre["where"]} if pre else None),
                "confidence": confidence_v1(side, pre),
                "confidence_rule": "v1-premarket-alignment",
                "card_picked_at": card.get("picked_at"),
                "card_rule_version": CARD_RULE_VERSION,
                "no_entry_windows_et": NO_ENTRY_WINDOWS_ET,
                "recorded_at": recorded_at,
                "backfilled": backfilled,
            }
            if card.get("card_source"):  # "rebuilt": re-picked later from saved data, not the card Sam saw
                rec["card_source"] = card["card_source"]
                rec["rebuild"] = card.get("rebuild")
            rec["sha256"] = canonical_hash(rec)
            out.append(rec)
    return out
