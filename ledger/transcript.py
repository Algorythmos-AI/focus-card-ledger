"""Recover IBKR get_price_history results from this Claude session's transcript, so bars are never retyped.

python -m ledger.transcript --since 2026-10-29T20:00:00Z --out /tmp/ibkr
writes one <contract_id>.json per contract (the newest result wins) and prints them.
A large result is saved by the harness to a file whose path is in the tool result text; that file is used.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .common import parse_t

SAVED = re.compile(r"saved to (/\S+?\.txt)")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict))


def collect(since: str, root: Path = Path.home() / ".claude" / "projects") -> dict[int, dict]:
    t0 = parse_t(since)
    uses, out = {}, {}
    for f in sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime):
        for line in f.read_text().splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = d.get("timestamp")
            if ts and parse_t(ts) < t0:
                continue
            msg = d.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
                continue
            for b in msg["content"]:
                if b.get("type") == "tool_use" and b.get("name", "").endswith("get_price_history"):
                    uses[b["id"]] = b["input"]
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                    txt = _text(b.get("content"))
                    m = SAVED.search(txt)
                    try:
                        data = json.loads(Path(m.group(1)).read_text()) if m else json.loads(txt)
                    except (json.JSONDecodeError, OSError):
                        continue
                    if "time" in data:
                        inp = uses[b["tool_use_id"]]
                        out[int(inp["contract_id"])] = data | {"_request": inp}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = collect(a.since)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for cid, data in res.items():
        (Path(a.out) / f"{cid}.json").write_text(json.dumps(data))
        print(cid, data["_request"].get("security_type"), data["time"][0], data["time"][-1], len(data["time"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
