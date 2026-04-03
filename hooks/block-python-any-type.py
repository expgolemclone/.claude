#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block Any type usage in Python files."""

import json
import re
import sys

# typing.Any のインポートパターン
_IMPORT_ANY_RE = re.compile(r"from\s+typing\b.*\bAny\b")

# typing.Any の修飾名使用
_QUALIFIED_ANY_RE = re.compile(r"\btyping\.Any\b")

# 型アノテーション中の Any（大文字始まりで完全一致）
_BARE_ANY_RE = re.compile(r"\bAny\b")

# コメント行
_COMMENT_RE = re.compile(r"^\s*#")

# 誤検知を避けるための除外パターン（any() 組み込み関数等）
_FALSE_POSITIVE_RE = re.compile(r"\bany\s*\(", re.IGNORECASE)


def _contains_any_type(text: str) -> bool:
    """テキスト中に Any 型の使用が含まれるか判定する。"""
    for line in text.splitlines():
        if _COMMENT_RE.match(line):
            continue
        if _IMPORT_ANY_RE.search(line):
            return True
        if _QUALIFIED_ANY_RE.search(line):
            return True
        if _BARE_ANY_RE.search(line):
            if not _FALSE_POSITIVE_RE.search(line):
                return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        return

    if not content:
        return

    if _contains_any_type(content):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "Any 型の使用は禁止されています（config: no_any = true）。\n"
                    "具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
