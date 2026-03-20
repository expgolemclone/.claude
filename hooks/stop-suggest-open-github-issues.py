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
    raw = run(cwd, "gh", "issue", "list", "--state", "open", "--sort", "created", "--order", "asc", "--limit", "1", "--json", "number,title")
    if not raw:
        return

    try:
        issues = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    if not issues:
        return

    issue = issues[0]
    json.dump(
        {
            "decision": "block",
            "reason": f"Open issue found:\n  #{issue['number']}: {issue['title']}\n\nこのissueを実装しますか？",
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
