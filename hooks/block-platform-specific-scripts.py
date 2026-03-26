#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block platform-specific script creation.

.sh/.bash  → Windows非対応のためブロック
.ps1/.bat/.cmd → Linux非対応のためブロック
いずれも .py への変更を促す。
"""

import json
import os
import sys

UNIX_ONLY_EXTENSIONS = {".sh", ".bash"}
WINDOWS_ONLY_EXTENSIONS = {".ps1", ".bat", ".cmd"}


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path:
        return

    ext = os.path.splitext(file_path)[1].lower()

    if ext in UNIX_ONLY_EXTENSIONS:
        json.dump(
            {
                "decision": "block",
                "reason": f"それはWindowsでは使えません。.pyにしてください。（{ext}）",
            },
            sys.stdout,
        )
    elif ext in WINDOWS_ONLY_EXTENSIONS:
        json.dump(
            {
                "decision": "block",
                "reason": f"それはLinuxでは使えません。.pyにしてください。（{ext}）",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
