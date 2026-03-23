#!/usr/bin/env python3
"""PreToolUse hook: block git commit messages containing prohibited keywords."""

import json
import re
import sys

BLOCKED_KEYWORDS = ["authored", "claude", "anthropic"]


def extract_commit_portion(command: str) -> str:
    """Extract the portion of the command starting from ``git commit``."""
    match = re.search(r"\bgit\s+commit\b", command)
    if match:
        return command[match.start():]
    return ""


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    commit_part = extract_commit_portion(command)
    if not commit_part:
        return

    for keyword in BLOCKED_KEYWORDS:
        if re.search(keyword, commit_part, re.IGNORECASE):
            json.dump(
                {
                    "decision": "block",
                    "reason": f"commit メッセージに '{keyword}' を含めることは禁止されています。git add と git commit は別コマンドで実行してください。",
                },
                sys.stdout,
            )
            return


if __name__ == "__main__":
    main()
