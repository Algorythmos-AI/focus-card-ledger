"""Checks run by CI on every push and by the daily jobs before committing.

1. Every record has its schema's required keys and a correct sha256.
2. A live (not backfilled) prediction was recorded before 09:30 New York on its session.
3. Every outcome points to an existing prediction whose hash matches.
4. Prediction files already on the base branch were not changed (append-only ledger).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime

from .common import NY, ROOT, canonical_hash, parse_t, read_jsonl


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


def main(argv=None) -> int:
    base = (argv or sys.argv[1:] or [None])[0]
    errs = check(base)
    for e in errs:
        print("ERROR", e)
    print("ok" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
