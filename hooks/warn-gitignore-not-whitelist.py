#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): warn when .gitignore is not in whitelist form.

Whitelist form = first non-comment, non-blank line starts with `*` (ignore everything),
followed by `!` negation patterns to selectively allow files.
"""


import json
import os
import sys


def _is_whitelist_form(content: str) -> bool:
    """Return True if .gitignore content follows whitelist convention."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped.startswith("*")
    return False


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if os.path.basename(file_path) != ".gitignore":
        return

    # Read the file after edit/write
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return

    if _is_whitelist_form(content):
        return

    json.dump(
        {
            "decision": "stop",
            "reason": (
                ".gitignore が whitelist 形式ではありません。\n"
                "最初の実効行を `*` にして、`!pattern` で許可する形式にしてください。\n"
                "例:\n"
                "  *\n"
                "  !.gitignore\n"
                "  !src/\n"
                "  !src/**"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
