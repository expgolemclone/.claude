#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): block non-Python scripts in hooks/ directory."""

import json
import os
import sys

BLOCKED_EXTENSIONS = {".sh", ".bash", ".js", ".ts", ".bat", ".ps1", ".rb", ".pl"}


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if "/.claude/hooks/" not in file_path:
        return

    ext = os.path.splitext(file_path)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        json.dump(
            {
                "decision": "block",
                "reason": f"hookスクリプトはPythonで作成してください（{ext} は許可されていません）",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
