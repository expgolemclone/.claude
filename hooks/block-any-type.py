#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block Any type usage in Python, Go, and Rust files."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from any_type_core import CHECKERS


def main() -> None:
    data = json.load(sys.stdin)
    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    ext = ""
    for e in CHECKERS:
        if file_path.endswith(e):
            ext = e
            break
    if not ext:
        return

    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        return

    if not content:
        return

    checker, suggestion = CHECKERS[ext]
    if checker(content):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "Any 型の使用は禁止されています（config: no_any = true）。\n"
                    f"{suggestion}"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
