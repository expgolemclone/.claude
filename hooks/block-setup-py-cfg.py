#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block setup.py and setup.cfg."""

import json
import os
import sys

PROHIBITED_NAMES = {"setup.py", "setup.cfg"}


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path:
        return

    # Claude Code設定ジェネレーター（~/.claude/setup.py）は対象外
    if os.path.join(".claude", "") in file_path:
        return

    basename = os.path.basename(file_path)
    if basename in PROHIBITED_NAMES:
        json.dump(
            {
                "decision": "block",
                "reason": f"{basename} は使用禁止です。pyproject.toml (PEP 621) を使用してください。",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
