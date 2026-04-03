#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block wildcard version specifiers in pyproject.toml."""

import json
import re
import sys

# "*" or '*' (standalone wildcard as version)
_WILDCARD_RE = re.compile(r"""['"](\s*\*\s*)['"]""")


def main() -> None:
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not file_path.endswith("pyproject.toml"):
        return

    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        return

    if not content:
        return

    if _WILDCARD_RE.search(content):
        json.dump(
            {
                "decision": "block",
                "reason": 'ワイルドカードバージョン（"*"）は禁止です。具体的なバージョン範囲を指定してください。',
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
