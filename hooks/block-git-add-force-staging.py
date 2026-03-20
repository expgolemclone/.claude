#!/usr/bin/env python3
"""PreToolUse hook: block git add -f/--force."""

import json
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    # Remove quoted strings to avoid false positives from commit messages etc.
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)

    if re.search(r"\bgit\s+add\b", stripped) and re.search(r"\s(-f|--force)\b", stripped):
        json.dump(
            {
                "decision": "block",
                "reason": "git add -f (--force) は禁止されています。.gitignore のルールを迂回する強制ステージングは許可されていません。",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
