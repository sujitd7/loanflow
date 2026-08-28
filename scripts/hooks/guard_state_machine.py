#!/usr/bin/env python3
"""PostToolUse hook: flag raw status writes in router/service code.

Convention: loan-file and review-task state changes must go through
`transition()` in api/app/services/state_machine.py, never a direct
`obj.status = ...` assignment. This nudges (exit 2 -> message to the model)
when a router assigns .status directly.
"""
import json
import os
import re
import sys

PATTERN = re.compile(r"^\s*[\w.\[\]\"']+\.status\s*=\s*(?!=)", re.MULTILINE)
WATCHED = ("api/app/routers/", "api/app/services/")
ALLOWED = ("state_machine.py",)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    fp = (data.get("tool_input") or {}).get("file_path", "") or ""
    if not fp or not os.path.isfile(fp):
        return 0

    root = data.get("cwd") or os.getcwd()
    try:
        rel = os.path.relpath(fp, root).replace("\\", "/")
    except ValueError:
        return 0

    if not rel.startswith(WATCHED) or rel.endswith(ALLOWED):
        return 0

    try:
        text = open(fp, encoding="utf-8").read()
    except Exception:
        return 0

    hits = [m.group(0).strip() for m in PATTERN.finditer(text)]
    if hits:
        sys.stderr.write(
            f"state-machine hook: {rel} assigns `.status` directly:\n"
            + "".join(f"  {h}\n" for h in hits[:5])
            + "Route status changes through transition() in "
            "api/app/services/state_machine.py instead.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
