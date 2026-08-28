#!/usr/bin/env python3
"""SessionStart hook: print current status, git branch, and the next roadmap item."""
import json
import os
import subprocess
import sys


def read(root, path):
    fp = os.path.join(root, path)
    try:
        return open(fp, encoding="utf-8").read()
    except Exception:
        return ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    root = data.get("cwd") or os.getcwd()

    parts = []

    status = read(root, "docs/STATUS.md").strip()
    if status:
        parts.append(status)

    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if branch:
            parts.append(f"Git branch: {branch}")
    except Exception:
        pass

    for line in read(root, "docs/ROADMAP.md").splitlines():
        if line.lstrip().startswith("- [ ]"):
            parts.append("Next roadmap item: " + line.split("]", 1)[1].strip())
            break

    if parts:
        print("\n\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
