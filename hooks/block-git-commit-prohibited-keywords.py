#!/usr/bin/env python3
"""PreToolUse hook: block git commit messages containing prohibited keywords."""

import json
import re
import sys

BLOCKED_KEYWORDS = ["authored", "claude", "anthropic"]


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\bgit\s+commit\b", command):
        return

    for keyword in BLOCKED_KEYWORDS:
        if re.search(keyword, command, re.IGNORECASE):
            json.dump(
                {
                    "decision": "block",
                    "reason": f"commit メッセージに '{keyword}' を含めることは禁止されています。",
                },
                sys.stdout,
            )
            return


if __name__ == "__main__":
    main()
