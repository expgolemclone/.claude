#!/usr/bin/env python3
"""Stop hook: suggest open issues in the current git repository."""

import json
import subprocess
import sys


def run(cwd: str, *args: str) -> str:
    result = subprocess.run(
        [*args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    cwd = data.get("cwd", "")

    # Check if we're in a git repository
    if not run(cwd, "git", "rev-parse", "--is-inside-work-tree"):
        return

    # Fetch open issues via gh CLI
    raw = run(cwd, "gh", "issue", "list", "--state", "open", "--limit", "10", "--json", "number,title")
    if not raw:
        return

    issues = json.loads(raw)
    if not issues:
        return

    lines = "\n".join(f"  #{i['number']}: {i['title']}" for i in issues)
    json.dump(
        {
            "decision": "block",
            "reason": f"Open issues found:\n{lines}\n\nこれらのissueを実装しますか？",
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
