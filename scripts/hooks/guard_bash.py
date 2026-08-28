#!/usr/bin/env python3
"""PreToolUse hook: block dangerous Bash commands. Exit 2 = blocked."""
import json
import re
import sys

DENY = [
    (r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME|\*)(\s|$)", "recursive delete of a top-level path"),
    (r"\bgit\s+push\b.*--force(?!-with-lease)", "force push without --force-with-lease"),
    (r"\bgit\b.*--no-verify\b", "bypassing git hooks (--no-verify)"),
    (r"\bdocker\s+compose\s+down\b.*(-v\b|--volumes\b)", "this deletes the local database volume"),
    (r"\bdrop\s+database\b", "dropping a database"),
    (r"\bfly\s+(deploy|apps\s+destroy|postgres\s+.*destroy)\b", "deploys/destroys must run through CI on main"),
    (r"\bpsql\b.*(amazonaws\.com|\.fly\.dev|render\.com|neon\.tech|supabase\.co)", "looks like a production database URL"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b", "piping a remote script straight into a shell"),
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    for pattern, why in DENY:
        if re.search(pattern, cmd, re.IGNORECASE):
            sys.stderr.write(
                f"guard-bash hook blocked this command: {why}.\n"
                f"  {cmd}\n"
                "If you really mean it, run it yourself outside Claude Code.\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
