#!/usr/bin/env python3
"""PreToolUse hook (Bash): block prohibited Python toolchains and enforce uv."""

import json
import re
import sys

# コマンド位置の境界: 行頭、&&、||、;、|、`、$(
_CMD_BOUNDARY = r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)"
_SUDO = r"(?:sudo\s+)?"

_PROHIBITED_CMD_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"(pyenv|conda|pipenv|poetry)\b"
)
_PIP_CMD_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"pip3?\b"
)


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    if not command:
        return

    # Remove quoted strings to avoid false positives
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)

    match = _PROHIBITED_CMD_RE.search(stripped)
    if match:
        tool = match.group(1)
        json.dump(
            {
                "decision": "block",
                "reason": f"{tool} は使用禁止です。代わりに uv を使用してください。",
            },
            sys.stdout,
        )
        return

    if _PIP_CMD_RE.search(stripped):
        json.dump(
            {
                "decision": "block",
                "reason": "pip の直接使用は禁止です。代わりに uv pip を使用してください。",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
