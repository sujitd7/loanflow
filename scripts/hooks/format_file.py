#!/usr/bin/env python3
"""PostToolUse hook: format and lint the file that was just written.

Uses host tooling when available (ruff for Python, the web's local prettier/eslint
or npx as a fallback). If a tool is missing it prints a one-line hint and exits 0 —
it never blocks the edit.
"""
import json
import os
import shutil
import subprocess
import sys


def run(cmd, cwd):
    try:
        subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=90)
    except Exception:
        pass


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

    notes = []

    if rel.startswith(("api/", "worker/")) and fp.endswith(".py"):
        if shutil.which("ruff"):
            run(["ruff", "format", fp], root)
            run(["ruff", "check", "--fix", fp], root)
        else:
            notes.append("`pip install ruff` to auto-format Python on save")
        if "/models" in rel or rel.endswith("models.py"):
            notes.append('models changed — run `make revision m="..."` for an Alembic migration')

    if rel.startswith("web/") and fp.endswith((".ts", ".tsx", ".css", ".json", ".md")):
        local = os.path.join(root, "web", "node_modules", ".bin")
        prettier = os.path.join(local, "prettier")
        eslint = os.path.join(local, "eslint")
        if os.path.exists(prettier):
            run([prettier, "--write", fp], root)
        elif shutil.which("npx"):
            run(["npx", "--yes", "prettier", "--write", fp], root)
        else:
            notes.append("install Node so the web files auto-format on save")
        if fp.endswith((".ts", ".tsx")) and os.path.exists(eslint):
            run([eslint, "--fix", fp], root)

    if notes:
        print("format-file hook: " + "; ".join(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
