#!/usr/bin/env python3
"""PreToolUse hook: block git commit messages containing prohibited keywords."""

import json
import re
import sys

BLOCKED_KEYWORDS = ["authored", "claude", "anthropic"]


def extract_message(command: str) -> str:
    """Extract the commit message portion after ``git commit -m``."""
    match = re.search(r"\bgit\s+commit\b.*?\s-m\s+", command)
    if match:
        return command[match.end():]
    return ""


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\bgit\s+commit\b", command):
        return

    message = extract_message(command)
    if not message:
        return

    for keyword in BLOCKED_KEYWORDS:
        if re.search(keyword, message, re.IGNORECASE):
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
