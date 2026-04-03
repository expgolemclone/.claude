#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block manual editing of requirements.txt."""

import json
import os
import re
import sys

_REQ_RE = re.compile(r"^requirements.*\.txt$", re.IGNORECASE)


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path:
        return

    basename = os.path.basename(file_path)
    if _REQ_RE.match(basename):
        json.dump(
            {
                "decision": "block",
                "reason": "requirements.txt の手書き編集は禁止です。uv pip compile で生成してください。",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
