#!/usr/bin/env python3
"""PreToolUse hook: block git commit messages containing 'authored'."""

import json
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if re.search(r"\bgit\s+commit\b", command) and re.search(r"authored", command, re.IGNORECASE):
        json.dump(
            {
                "decision": "block",
                "reason": "commit メッセージに 'authored' を含めることは禁止されています。Co-Authored-By 等の記述を除去してください。",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
