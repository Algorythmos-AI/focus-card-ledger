"""Human-readable outputs: the README scorecard block, per-day pages and the weekly report."""
from __future__ import annotations

from .common import ROOT


def _pct(rate: dict) -> str:
    if not rate or rate["rate"] is None:
        return "–"
    lo, hi = rate["ci95"]
    return f'{rate["rate"]*100:.0f}% ({rate["k"]}/{rate["n"]}; 95% {lo*100:.0f}–{hi*100:.0f}%)'


def _r(x) -> str:
    return "–" if x is None else f"{x:+.2f}R"


def _usd(x) -> str:
    return "–" if x is None else f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def _rows(s: dict) -> list[tuple[str, str]]:
    return [
        ("Setups published", str(s["setups"])),
        ("Triggered", _pct(s["trigger_rate"])),
        ("Filled after the retest", _pct(s["fill_rate_of_triggered"])),
        ("Hit T1 before the stop", _pct(s["win_rate_t1_before_stop"])),
        ("Stopped", _pct(s["stop_rate"])),
        ("Reached T2", _pct(s["t2_hit_rate"])),
        ("Average R, card exits", _r(s["card_expectancy_r"])),
        ("Average R, 5-minute rule", _r(s["five_min_expectancy_r"])),
        ("Average R, hold for T2", _r(s["hold_t2_expectancy_r"])),
        ("Total R (card / 5-min / T2)", f'{_r(s["card_total_r"])} / {_r(s["five_min_total_r"])} / {_r(s["hold_t2_total_r"])}'),
        ("Option P&L, 1 contract (card / 5-min / T2)",
         f'{_usd(s["card_option_usd_total"])} / {_usd(s["five_min_option_usd_total"])} / {_usd(s["hold_t2_option_usd_total"])}'
         f' over {s["card_option_trades"]} trades'),
        ("Average best / worst move", f'{_r(s["avg_mfe_r"])} / {_r(s["avg_mae_r"])}'),
        ("Median minutes to T1", "–" if s["median_minutes_to_t1"] is None else f'{s["median_minutes_to_t1"]:.0f}'),
        ("Bias read right", _pct(s["bias_hit_rate"])),
    ]


def summary_table(s: dict) -> str:
    return "| Measure | Result |\n| --- | --- |\n" + "".join(f"| {a} | {b} |\n" for a, b in _rows(s))


TIER_NAMES = {"published": "Published cards", "rebuilt_5min": "Rebuilt, 5-min bars",
              "rebuilt_30min": "Rebuilt, 30-min bars", "rebuilt_60min": "Rebuilt, 60-min bars"}


def _span(a, b) -> str:
    from datetime import date
    fa, fb = date.fromisoformat(a), date.fromisoformat(b)
    return f"{fa.day} {fa:%b} – {fb.day} {fb:%b}"


def tier_table(tiers: dict) -> str:
    """One column per quality tier, so rough history sits next to the headline, never mixed into it."""
    names = [t for t in TIER_NAMES if t in tiers]
    cols = [dict(_rows(tiers[t])) for t in names]
    head = "| Measure | " + " | ".join(f'{TIER_NAMES[t]} ({_span(*tiers[t]["sessions"])})' for t in names) + " |"
    out = [head, "| --- |" + " --- |" * len(names)]
    for label, _ in _rows(tiers[names[0]]):
        out.append(f"| {label} | " + " | ".join(c[label] for c in cols) + " |")
    return "\n".join(out) + "\n"


def slice_table(by: dict, key: str, labels: dict | None = None) -> str:
    out = ["| Group | Setups | Bias read right | Triggered | Hit T1 before the stop | Average R, card |",
           "| --- | --- | --- | --- | --- | --- |"]
    for g, s in by.get(key, {}).items():
        out.append(f'| {(labels or {}).get(g, g)} | {s["setups"]} | {_pct(s["bias_hit_rate"])} | {_pct(s["trigger_rate"])} '
                   f'| {_pct(s["win_rate_t1_before_stop"])} | {_r(s["card_expectancy_r"])} |')
    return "\n".join(out) + "\n"


def day_table(rows: list[dict]) -> str:
    out = ["| Setup | Level → entry / stop / T1 / T2 | Result | R card | R 5-min | Option $ |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        res = r["result"].replace("_", " ")
        out.append(f'| {r["symbol"]} {r["side"]} (#{r["rank"]}, {r["bias"]}) | {r["level"]} → {r["entry"]} / {r["stop"]} / {r["t1"]} / {r["t2"]} '
                   f'| {res} | {_r(r["r_card"])} | {_r(r["r_five_min"])} | {_usd(r.get("opt_usd_card"))} |')
    return "\n".join(out) + "\n"


def readme_block(card: dict, rows: list[dict]) -> str:
    last = card["as_of_session"]
    lines = [f"Last scored session: **{last}** · {card['published_sessions']} sessions of published cards"
             f" · {card['sessions'] - card['published_sessions']} sessions of rebuilt history.", "",
             "### Published cards", "", summary_table(card["published"]),
             "### Last 20 published sessions", "", summary_table(card["rolling_20"])]
    if len(card.get("tiers", {})) > 1:
        cal = card["calibration_rebuilt"]
        lines += ["### Rebuilt history, by bar size", "",
                  "Cards re-picked from saved data with the card's own code (`tools/rebuild_cards.py`). Coarse bars miss "
                  "many retest fills, so read fill and R numbers here as rough; the bias, trigger and day-range facts hold "
                  "on any bar size. `reports/tier_check.json` measures the gap.", "",
                  tier_table(card["tiers"]),
                  f"Card score vs R (information coefficient), rebuilt history: {cal['ic_card_score_vs_r']}; "
                  f"rank vs R: {cal['ic_rank_vs_r']}.", "",
                  "#### Rebuilt history by bias", "", slice_table(card["by_rebuilt"], "bias"),
                  "#### Rebuilt history by where the stock opened", "",
                  slice_table(card["by_rebuilt"], "open_gap", {"opened_inside": "Opened between floor and ceiling",
                                                                "opened_over_ceiling": "Opened over the ceiling",
                                                                "opened_under_floor": "Opened under the floor"}),
                  "#### Rebuilt history by card rank", "", slice_table(card["by_rebuilt"], "rank"),
                  "#### Rebuilt history by how far the level was from the close", "", slice_table(card["by_rebuilt"], "distance")]
    lines += [f"### {last}", "", day_table([r for r in rows if r["session"] == last])]
    return "\n".join(lines)


def write_readme(card: dict, rows: list[dict]) -> None:
    p = ROOT / "README.md"
    text = p.read_text()
    a, b = "<!-- scorecard:start -->", "<!-- scorecard:end -->"
    head, rest = text.split(a, 1)
    _, tail = rest.split(b, 1)
    p.write_text(head + a + "\n" + readme_block(card, rows) + "\n" + b + tail)


def write_day(session: str, rows: list[dict]) -> None:
    p = ROOT / "reports" / "daily" / session[:4] / f"{session}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {session}\n\nStock R before option costs. Option $ is one contract on IBKR last-trade bars.\n\n" + day_table(rows))


def write_week(label: str, card_week: dict, card_all: dict, rows: list[dict]) -> None:
    p = ROOT / "reports" / "weekly" / f"{label}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    cal = card_all["calibration"]
    conf = " · ".join(f"{k}: {_pct(v)}" for k, v in cal["win_rate_by_confidence"].items())
    body = [f"# Week {label}", "", "## This week", "", summary_table(card_week), "## Since the start", "",
            summary_table(card_all["published"]),
            "## Does the card know its best setups?", "",
            f"- Rank vs R (information coefficient): {cal['ic_rank_vs_r']}",
            f"- Card score vs R: {cal['ic_card_score_vs_r']}",
            f"- T1 win rate by confidence: {conf}", "",
            "Small samples: read the ranges, not the point estimates.", "",
            "## Setups this week", "", day_table(rows)]
    p.write_text("\n".join(body))
