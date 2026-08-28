#!/usr/bin/env python3
"""Stop hook: run the backend test suite so an agentic loop can't 'finish' on red.

Opt-in: set LOANFLOW_TEST_ON_STOP=1 in your environment to enable it. Off by
default because it needs either a local pytest or a running Docker daemon.
Exit 2 -> the model is told the work isn't done.
"""
import json
import os
import shutil
import subprocess
import sys


def main() -> int:
    if os.environ.get("LOANFLOW_TEST_ON_STOP") != "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0

    root = data.get("cwd") or os.getcwd()

    if shutil.which("pytest"):
        cmd, cwd = ["pytest", "-q"], os.path.join(root, "api")
    elif shutil.which("docker"):
        cmd, cwd = ["docker", "compose", "run", "--rm", "api", "pytest", "-q"], root
    else:
        return 0

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
        sys.stderr.write("Stop hook: backend tests are failing — the task is not done.\n" + tail + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
