"""Command line: python -m ledger <command> ...

  predict   --card PATH [--recorded-at ISO] [--backfilled]       before the open: card -> predictions
  bars      --session D --name NAME --ibkr FILE [--kind OPT]      store IBKR bars (splits multi-day files)
  score     [--session D | --all] [--recorded-at ISO]             after the close: predictions + bars -> outcomes
  options   --session D --manifest FILE                           C: choose a contract per filled setup, score it
  scorecard                                                       rebuild scorecard.json, data/setups.csv, README
  report    --week YYYY-Www                                       B: weekly report
  dashboard --session D [--out FILE] [--send]                     the day's edition for Sam's dashboard
  validate  [BASE_REF]                                            CI checks
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import bars as barsmod
from . import card as cardmod
from . import dashboard, metrics, options, report, score, validate
from .common import ROOT, canonical_hash, day_path, read_jsonl, write_jsonl


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cmd_predict(a):
    card = json.loads(Path(a.card).read_text())
    recs = cardmod.predictions_from_card(card, recorded_at=a.recorded_at or now(), backfilled=a.backfilled)
    path = day_path("predictions", card["session"])
    old = read_jsonl(path)
    if old:
        same = [{k: v for k, v in r.items() if k not in ("recorded_at", "sha256")} for r in old] == \
               [{k: v for k, v in r.items() if k not in ("recorded_at", "sha256")} for r in recs]
        print(f"{path.relative_to(ROOT)} exists ({'unchanged' if same else 'CARD CHANGED - not overwritten'})")
        return 0 if same else 3
    write_jsonl(path, recs)
    print(f"wrote {len(recs)} predictions to {path.relative_to(ROOT)}")
    return 0


def cmd_bars(a):
    resp = json.loads(Path(a.ibkr).read_text())
    days = barsmod.split_ibkr(resp, symbol=a.name.split("_")[0], kind=a.kind)
    for d, day in days.items():
        if (a.session and d != a.session) or not day_path("predictions", d).exists():
            continue
        p = barsmod.save_day(d, a.name, day)
        print(f"{d} {a.name}: {len(day['time'])} bars -> {p.relative_to(ROOT)}")
    return 0


def _score_session(session: str, recorded_at: str) -> int:
    preds = read_jsonl(day_path("predictions", session))
    if not preds:
        print(f"{session}: no predictions")
        return 2
    outs, missing = [], []
    for p in preds:
        B, h = barsmod.load_day(session, p["symbol"])
        if B is None or not barsmod.is_complete(B):
            missing.append(p["symbol"])
            continue
        outs.append(score.score(p, B, bars_sha256=h, recorded_at=recorded_at))
    if missing:
        print(f"{session}: bars missing or incomplete for {sorted(set(missing))}; nothing written")
        return 1
    write_jsonl(day_path("outcomes", session), outs)
    print(f"{session}: scored {len(outs)} setups")
    return 0


def cmd_score(a):
    sessions = sorted(f.stem for f in (ROOT / "predictions").rglob("*.jsonl")) if a.all else [a.session]
    return max(_score_session(s, a.recorded_at or now()) for s in sessions)


def cmd_options(a):
    """manifest: {"<id>": {"expiry": "20261028", "chain": {"<strike>": {"name": "AVGO_347.5C", "description": "..."}}}}"""
    man = json.loads(Path(a.manifest).read_text())
    outs = {o["id"]: o for o in read_jsonl(day_path("outcomes", a.session))}
    recs = []
    for oid, o in outs.items():
        if not o.get("filled"):
            continue
        m = man.get(oid)
        if not m:
            recs.append(options.score_option(o, strike=None, expiry=None, description=None, bars=None,
                                             bars_sha256=None, recorded_at=now(), note="no option data pulled"))
            continue
        chain = []
        for strike, c in m["chain"].items():
            B, h = barsmod.load_day(a.session, c["name"])
            if B is not None:
                chain.append((float(strike), B | {"_sha": h, "_desc": c.get("description")}))
        pick = options.choose(o["side"], next(p for p in read_jsonl(day_path("predictions", a.session)) if p["id"] == oid)["entry"],
                              o["fill_time"], chain)
        if pick is None:
            recs.append(options.score_option(o, strike=None, expiry=m["expiry"], description=None, bars=None,
                                             bars_sha256=None, recorded_at=now(),
                                             note="no strike at or under $2.00 among those pulled"))
            continue
        strike, B, _ = pick
        recs.append(options.score_option(o, strike=strike, expiry=m["expiry"], description=B["_desc"],
                                         bars={k: v for k, v in B.items() if not k.startswith("_")},
                                         bars_sha256=B["_sha"], recorded_at=now()))
    write_jsonl(day_path("options", a.session), recs)
    print(f"{a.session}: {sum(1 for r in recs if r['policies'])} option trades scored, {len(recs)} records")
    return 0


def cmd_scorecard(a):
    rows = metrics.load()
    card = metrics.scorecard(rows)
    (ROOT / "scorecard.json").write_text(json.dumps(card, indent=1, sort_keys=True) + "\n")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "setups.csv").write_text(metrics.to_csv(rows))
    pq = metrics.export_parquet(rows, ROOT / "data" / "setups.parquet")
    for s in sorted({r["session"] for r in rows}):
        report.write_day(s, [r for r in rows if r["session"] == s])
    report.write_readme(card, rows)
    print(f"scorecard: {len(rows)} setups, {card['sessions']} sessions{', parquet written' if pq else ''}")
    return 0


def cmd_report(a):
    rows = metrics.load()
    y, w = a.week.split("-W")
    week_rows = [r for r in rows if date.fromisoformat(r["session"]).isocalendar()[:2] == (int(y), int(w))]
    report.write_week(a.week, metrics.summarize(week_rows), metrics.scorecard(rows), week_rows)
    print(f"reports/weekly/{a.week}.md ({len(week_rows)} setups)")
    return 0


def cmd_dashboard(a):
    doc = dashboard.build(a.session)
    body = json.dumps(doc, separators=(",", ":"))
    if a.out:
        Path(a.out).write_text(body + "\n")
    d = doc["day"]
    print(f"{a.session}: {len(doc['names'])} names, {d['filled']} fills, {d['r']:+.2f}R, {len(body):,} bytes, run {doc['run_id']}")
    if not a.send:
        return 0
    status, text = dashboard.send(doc)
    print(f"dashboard: {status} {text}")
    return 0 if status == 200 else 2 if status == 2 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict"); p.add_argument("--card", required=True); p.add_argument("--recorded-at"); p.add_argument("--backfilled", action="store_true")
    p = sub.add_parser("bars"); p.add_argument("--name", required=True); p.add_argument("--ibkr", required=True); p.add_argument("--session"); p.add_argument("--kind", default="STK")
    p = sub.add_parser("score"); p.add_argument("--session"); p.add_argument("--all", action="store_true"); p.add_argument("--recorded-at")
    p = sub.add_parser("options"); p.add_argument("--session", required=True); p.add_argument("--manifest", required=True)
    sub.add_parser("scorecard")
    p = sub.add_parser("report"); p.add_argument("--week", required=True)
    p = sub.add_parser("validate"); p.add_argument("base", nargs="?")
    p = sub.add_parser("dashboard"); p.add_argument("--session", required=True); p.add_argument("--out"); p.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        return validate.main([a.base] if a.base else [])
    return {"predict": cmd_predict, "bars": cmd_bars, "score": cmd_score, "options": cmd_options,
            "scorecard": cmd_scorecard, "report": cmd_report, "dashboard": cmd_dashboard}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
