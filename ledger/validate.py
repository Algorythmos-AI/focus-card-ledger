"""Checks run by CI on every push and by the daily jobs before committing.

1. Every record has its schema's required keys and a correct sha256.
2. A live (not backfilled) prediction was recorded before 09:30 New York on its session.
3. Every outcome points to an existing prediction whose hash matches.
4. Prediction files already on the base branch were not changed (append-only ledger).
5. With --gaps: every past NYSE session since the first one in the ledger has predictions and outcomes, or is listed
   in missed_sessions.json with the reason. Like predictions, that list is append-only against the base branch, so a
   missed session stays listed; a later back-fill of it is marked `backfilled: true` (check 2 already refuses
   predictions recorded after the open without that mark).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

from .common import NY, ROOT, canonical_hash, parse_t, read_jsonl
from .sessions import covered, is_session, sessions_between

MISSED = "missed_sessions.json"
KINDS = ("predictions", "outcomes")
# New York times by which a session's record must exist: the open for predictions (a live prediction is saved before
# it), and 17:00 for outcomes, about 40 minutes after the after-close run starts (16:21).
DUE = {"predictions": time(9, 30), "outcomes": time(17, 0)}


def required(kind: str) -> list[str]:
    return json.loads((ROOT / "schema" / f"{kind}.schema.json").read_text())["required"]


def check(base_ref: str | None = None) -> list[str]:
    errs: list[str] = []
    preds = {}
    for kind, folder in (("prediction", "predictions"), ("outcome", "outcomes"), ("option_outcome", "options")):
        req = required(kind)
        for f in sorted((ROOT / folder).rglob("*.jsonl")):
            for i, r in enumerate(read_jsonl(f), 1):
                where = f"{f.relative_to(ROOT)}:{i}"
                miss = [k for k in req if k not in r]
                if miss:
                    errs.append(f"{where} missing {miss}")
                if r.get("sha256") != canonical_hash(r):
                    errs.append(f"{where} sha256 does not match its content")
                if kind == "prediction":
                    preds[r["id"]] = r
                    if not r.get("backfilled"):
                        d = datetime.fromisoformat(r["session"])
                        open_ny = datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY)
                        if parse_t(r["recorded_at"]) >= open_ny:
                            errs.append(f"{where} recorded after the open but not marked backfilled")
                if kind == "outcome":
                    p = preds.get(r["id"])
                    if p is None:
                        errs.append(f"{where} has no prediction")
                    elif p["sha256"] != r["prediction_sha256"]:
                        errs.append(f"{where} prediction hash mismatch")
    if base_ref:
        diff = subprocess.run(["git", "diff", "--name-status", base_ref, "--", "predictions/"],
                              cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
        for line in filter(None, diff):
            status, path = line.split("\t", 1)
            if status != "A":
                errs.append(f"{path}: predictions are append-only (status {status} vs {base_ref})")
    return errs


def due(session: str, kind: str) -> datetime:
    return datetime.combine(date.fromisoformat(session), DUE[kind], tzinfo=NY)


def find_gaps(predicted: dict[str, bool], scored: set[str], missed: list, now: datetime) -> list[str]:
    """Sessions the ledger should hold but does not.

    predicted: session -> True if any of its predictions is live (not backfilled). scored: sessions with outcomes.
    missed: the entries of missed_sessions.json. now: the time of the check (timezone-aware).
    """
    errs: list[str] = []
    today = now.astimezone(NY).date()
    if not covered(today):
        return [f"today ({today}) is outside the session calendar; extend ledger/sessions.py"]
    have = {"predictions": set(predicted), "outcomes": set(scored)}

    listed: dict[str, set[str]] = {}
    if not isinstance(missed, list):
        errs.append(f"{MISSED} must be a list of entries")
        missed = []
    for i, m in enumerate(missed, 1):
        where = f"{MISSED} entry {i}"
        if not isinstance(m, dict):
            errs.append(f"{where} is not an object")
            continue
        s, kinds = m.get("session"), m.get("missing")
        try:
            open_ = is_session(s)
        except (TypeError, ValueError):
            errs.append(f"{where}: session {s!r} is not a date in the calendar")
            continue
        if not open_:
            errs.append(f"{where}: NYSE was closed on {s}, so nothing was missed")
            continue
        if s in listed:
            errs.append(f"{where}: {s} is listed twice")
            continue
        if not isinstance(kinds, list) or not kinds or any(k not in KINDS for k in kinds) or len(set(kinds)) != len(kinds):
            errs.append(f"{where}: {s} 'missing' must list one or both of {list(KINDS)}")
            continue
        if not str(m.get("reason") or "").strip():
            errs.append(f"{where}: {s} needs a reason")
        for k in kinds:
            if now < due(s, k):
                errs.append(f"{where}: {s} {k} are not due until {DUE[k]:%H:%M} New York that day; list a session only once it was missed")
        if "predictions" in kinds and predicted.get(s):
            errs.append(f"{where}: {s} is listed as missed but has live predictions; remove the entry")
        listed[s] = set(kinds)

    valid = []
    for k, sessions in have.items():
        for s in sorted(sessions):
            try:
                open_ = is_session(s)
            except ValueError as e:
                errs.append(f"{k}: {s} is not a date in the calendar ({e})")
                continue
            if not open_:
                errs.append(f"{k}/{s[:4]}/{s}.jsonl: NYSE was closed on {s}")
            elif k == "predictions":
                valid.append(s)
    if not valid:
        return errs
    for s in sessions_between(date.fromisoformat(min(valid)), today):
        for k in KINDS:
            if now >= due(s, k) and s not in have[k] and k not in listed.get(s, set()):
                errs.append(f"{s}: no {k}, and NYSE was open (due {DUE[k]:%H:%M} New York). List it in {MISSED} "
                            f"with the reason; never back-fill it silently")
    return errs


def ledger_sessions(root: Path = ROOT) -> tuple[dict[str, bool], set[str]]:
    predicted = {}
    for f in (root / "predictions").rglob("*.jsonl"):
        rows = read_jsonl(f)
        if rows:
            predicted[f.stem] = any(not r.get("backfilled") for r in rows)
    scored = {f.stem for f in (root / "outcomes").rglob("*.jsonl") if read_jsonl(f)}
    return predicted, scored


def dropped_entries(base_missed: list, missed: list) -> list[str]:
    """Sessions listed on the base branch that this tree no longer lists."""
    def sessions(entries):
        return {m.get("session") for m in entries if isinstance(m, dict)} if isinstance(entries, list) else set()
    return [f"{MISSED}: {s} was listed on the base branch and is gone; the list is append-only"
            for s in sorted(sessions(base_missed) - sessions(missed), key=str)]


def check_gaps(now: datetime | None = None, root: Path = ROOT, base_ref: str | None = None) -> list[str]:
    path = root / MISSED
    missed = json.loads(path.read_text()) if path.exists() else []
    predicted, scored = ledger_sessions(root)
    errs = find_gaps(predicted, scored, missed, now or datetime.now(timezone.utc))
    if base_ref:
        old = subprocess.run(["git", "show", f"{base_ref}:{MISSED}"], cwd=root, capture_output=True, text=True)
        if old.returncode == 0:
            errs += dropped_entries(json.loads(old.stdout), missed)
    return errs


def parse_args(argv: list[str]) -> tuple[str | None, bool]:
    args = [a for a in argv if a != "--gaps"]
    if len(args) > 1:
        raise SystemExit(f"validate takes at most one BASE_REF, got {args}")
    return (args[0] if args else None), "--gaps" in argv


def main(argv=None) -> int:
    base, gaps = parse_args(list(sys.argv[1:] if argv is None else argv))
    errs = check(base) + (check_gaps(base_ref=base) if gaps else [])
    for e in errs:
        print("ERROR", e)
    print("ok" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
