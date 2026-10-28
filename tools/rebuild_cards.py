"""Rebuild the Top 4 Focus Card for past sessions, so they can be scored like the live ones.

python tools/rebuild_cards.py --out /tmp/cards [--from 2026-03-04] [--to 2026-10-16]

Uses the card's own code (options-levels skill: olib.levels_for and focus.pick), never a copy of it:
- sessions with a saved levels file (12 Oct 2026 on) are picked from that file and that day's iv_history row;
- older sessions get their levels rebuilt from IBKR daily bars, the same way run.py builds them. There is no
  option-volume snapshot for those days, so pick() falls back to 1.0x normal volume.
Each card is tagged card_source "rebuilt" with a `rebuild` note saying which inputs it had.

--check also re-picks the sessions that have a published card and reports how often the rebuild matches it,
with and without the option-volume input. That is the error bar on every rebuilt card.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path("/mnt/project-files/skills/options-levels/scripts")
DATA = Path("/mnt/project-files/options-tab/data")
DAILY = Path("/mnt/project-files/options-tab/bars_daily_2y_10names_2026-10-09.json")
NAMES = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "PLTR"]


def _skill(path: Path):
    sys.path.insert(0, str(path))
    import focus
    import olib
    import run
    return focus, olib, run


def levels_from_daily(olib, run, daily: dict, session: str) -> dict:
    finished = olib.prev_session(session)
    since = (dt.date.fromisoformat(finished) - dt.timedelta(days=420)).isoformat()
    tickers, problems = {}, {}
    for t in NAMES:
        ld = olib.load_ibkr(daily[t], since=since)
        bars = [b for b in ld.bars if b.d <= finished]
        if not bars or bars[-1].d != finished:
            problems[t] = [f"no daily bar for {finished}"]
            continue
        tickers[t] = run.jsonable(olib.levels_for(bars, session))
    return {"schema": "stocksdelta/options-levels", "version": 0, "session": session, "built_from": finished,
            "source": "IBKR daily bars, rebuilt by focus-card-ledger tools/rebuild_cards.py",
            "tickers": tickers, "problems": problems}


def pick(focus, tmp: Path, session: str, *, no_iv: bool = False) -> dict:
    if no_iv:
        (tmp / "iv_history.csv").write_text("session,ticker\n")
    _, doc = focus.pick(session, tmp)
    return doc


def workdir(levels: dict[str, dict] | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cards-"))
    (tmp / "levels").mkdir()
    for f in (DATA / "levels").glob("*.json"):
        shutil.copy(f, tmp / "levels" / f.name)
    shutil.copy(DATA / "iv_history.csv", tmp / "iv_history.csv")
    for s, doc in (levels or {}).items():
        (tmp / "levels" / f"{s}.json").write_text(json.dumps(doc))
    return tmp


def key(doc: dict) -> list:
    return [(i["symbol"], i["rank"], i["bias"], i["breakout_above"], i["hold_above"],
             (i["target_up"] or {}).get("price"), (i["target_down"] or {}).get("price")) for i in doc["items"]]


def check(focus) -> dict:
    """Re-pick every session with a published card: does the rebuild give the same names and levels?"""
    out = {}
    for f in sorted((DATA / "focus").glob("*.json")):
        pub = json.loads(f.read_text())
        row = {}
        for label, no_iv in (("with_option_volume", False), ("without_option_volume", True)):
            doc = pick(focus, workdir(), pub["session"], no_iv=no_iv)
            pub_names, re_names = {i["symbol"] for i in pub["items"]}, {i["symbol"] for i in doc["items"]}
            pub_lv = {i["symbol"]: (i["breakout_above"], i["hold_above"], i["bias"]) for i in pub["items"]}
            same_lv = sum(1 for i in doc["items"] if pub_lv.get(i["symbol"]) == (i["breakout_above"], i["hold_above"], i["bias"]))
            row[label] = {"identical": key(doc) == key(pub), "names_matched": len(pub_names & re_names),
                          "same_levels_and_bias": same_lv, "of": len(pub["items"])}
        out[pub["session"]] = row
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="start", default="2026-03-04")
    ap.add_argument("--to", dest="end", default="2026-10-16")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--skill", default=str(SKILL))
    a = ap.parse_args(argv)
    focus, olib, run = _skill(Path(a.skill))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    have_files = {f.stem for f in (DATA / "levels").glob("*.json")}
    iv_sessions = {r["session"] for r in csv.DictReader(open(DATA / "iv_history.csv"))}
    daily = json.loads(DAILY.read_text())
    built = {}
    s = a.start if olib.is_session(a.start) else olib.next_session(a.start)
    while s <= a.end:
        if s not in have_files:
            built[s] = levels_from_daily(olib, run, daily, s)
        s = olib.next_session(s)
    tmp = workdir(built)
    n = 0
    for s in sorted(set(built) | {x for x in have_files if a.start <= x <= a.end}):
        doc = pick(focus, tmp, s)
        lv = json.loads((tmp / "levels" / f"{s}.json").read_text())
        doc["card_source"] = "rebuilt"
        doc["rebuild"] = {
            "tool": "tools/rebuild_cards.py",
            "levels": "saved levels file" if s in have_files else "rebuilt from IBKR daily bars",
            "option_volume": "iv_history" if lv["built_from"] in iv_sessions else "missing: 1.0x assumed",
            "premarket": "missing",
            "universe": sorted(lv["tickers"]),
        }
        doc["picked_at"] = None
        (out / f"{s}.json").write_text(json.dumps(doc, indent=1))
        n += 1
    print(f"rebuilt {n} cards into {out}")
    if a.check:
        res = check(focus)
        (out / "_check.json").write_text(json.dumps(res, indent=1))
        for s, r in res.items():
            print(s, r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
