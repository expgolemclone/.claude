#!/usr/bin/env python3
"""PostToolUse hook (Bash): run setup.py after git pull/commit in ~/.claude."""

import json
import re
import subprocess
import sys


def main() -> None:
    data = json.load(sys.stdin)
    cwd = data.get("cwd", "")
    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\bgit\s+(pull|commit)\b", command):
        return

    normalized = cwd.replace("\\", "/").rstrip("/")
    if not normalized.endswith("/.claude"):
        return

    result = subprocess.run(
        ["uv", "run", "python", "setup.py"],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )

    output = result.stdout.strip() or result.stderr.strip()
    if output:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"[auto] setup.py executed:\n{output}",
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
