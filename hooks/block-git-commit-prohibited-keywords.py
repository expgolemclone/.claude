#!/usr/bin/env python3
"""PreToolUse hook: block git commit messages containing prohibited keywords."""

import json
import re
import sys

BLOCKED_KEYWORDS = ["authored", "claude", "anthropic"]


def extract_message(command: str) -> str:
    """Extract the commit message from -m/--message argument or HEREDOC."""
    # HEREDOC: git commit -m "$(cat <<'EOF' ... EOF )"
    heredoc = re.search(r"<<'?(\w+)'?\s*\n(.*?)\n\1", command, re.DOTALL)
    if heredoc:
        return heredoc.group(2)

    # -m "..." or --message "..." or --message="..."
    msg = re.search(r'(?:-m|--message)[= ]\s*"((?:[^"\\]|\\.)*)"', command)
    if msg:
        return msg.group(1)

    msg = re.search(r"(?:-m|--message)[= ]\s*'((?:[^'\\]|\\.)*)'", command)
    if msg:
        return msg.group(1)

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
                    "reason": f"commit メッセージに '{keyword}' を含めることは禁止されています。",
                },
                sys.stdout,
            )
            return


if __name__ == "__main__":
    main()
