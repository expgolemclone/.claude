#!/usr/bin/env python3
"""Stop hook: block if there are uncommitted or unpushed changes in a git repo."""

import json
import subprocess
import sys


def run_git(cwd: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    cwd = data.get("cwd", "")

    # Check if we're in a git repository
    if not run_git(cwd, "rev-parse", "--is-inside-work-tree"):
        return

    issues = ""

    # Check for uncommitted changes
    uncommitted = run_git(cwd, "status", "--porcelain")
    if uncommitted:
        issues += f"Uncommitted changes detected:\n{uncommitted}\n\n"

    # Check for unpushed commits
    upstream = run_git(cwd, "rev-parse", "--abbrev-ref", "@{upstream}")
    if upstream:
        unpushed = run_git(cwd, "log", "@{upstream}..HEAD", "--oneline")
        if unpushed:
            issues += f"Unpushed commits detected:\n{unpushed}\n\n"

    if issues:
        json.dump(
            {
                "decision": "block",
                "reason": issues + "Commit and push all changes before finishing.",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
