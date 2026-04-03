#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block Any type usage in Python, Go, and Rust files."""

import json
import re
import sys
from typing import Callable

# ---------------------------------------------------------------------------
# Python patterns
# ---------------------------------------------------------------------------
_PY_IMPORT_ANY_RE = re.compile(r"from\s+typing\b.*\bAny\b")
_PY_QUALIFIED_ANY_RE = re.compile(r"\btyping\.Any\b")
_PY_BARE_ANY_RE = re.compile(r"\bAny\b")
_PY_COMMENT_RE = re.compile(r"^\s*#")
_PY_FALSE_POSITIVE_RE = re.compile(r"\bany\s*\(", re.IGNORECASE)


def _check_python(text: str) -> bool:
    for line in text.splitlines():
        if _PY_COMMENT_RE.match(line):
            continue
        if _PY_IMPORT_ANY_RE.search(line):
            return True
        if _PY_QUALIFIED_ANY_RE.search(line):
            return True
        if _PY_BARE_ANY_RE.search(line):
            if not _PY_FALSE_POSITIVE_RE.search(line):
                return True
    return False


# ---------------------------------------------------------------------------
# Go patterns
# ---------------------------------------------------------------------------
_GO_COMMENT_RE = re.compile(r"^\s*//")
_GO_IMPORT_RE = re.compile(r"^\s*import\s")
_GO_INTERFACE_EMPTY_RE = re.compile(r"\binterface\s*\{\s*\}")
_GO_ANY_TYPE_RE = re.compile(r"\bany\b")
_GO_ANY_IDENT_RE = re.compile(r"\w+any|any\w+", re.IGNORECASE)


def _check_go(text: str) -> bool:
    for line in text.splitlines():
        if _GO_COMMENT_RE.match(line):
            continue
        if _GO_IMPORT_RE.match(line):
            continue
        if _GO_INTERFACE_EMPTY_RE.search(line):
            return True
        if _GO_ANY_TYPE_RE.search(line) and not _GO_ANY_IDENT_RE.search(line):
            return True
    return False


# ---------------------------------------------------------------------------
# Rust patterns
# ---------------------------------------------------------------------------
_RS_COMMENT_RE = re.compile(r"^\s*//")
_RS_USE_ANY_RE = re.compile(r"\buse\s+std::any::Any\b")
_RS_DYN_ANY_RE = re.compile(r"\bdyn\s+Any\b")


def _check_rust(text: str) -> bool:
    for line in text.splitlines():
        if _RS_COMMENT_RE.match(line):
            continue
        if _RS_USE_ANY_RE.search(line):
            return True
        if _RS_DYN_ANY_RE.search(line):
            return True
    return False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
_CHECKERS: dict[str, tuple[Callable[[str], bool], str]] = {
    ".py": (_check_python, "具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。"),
    ".go": (_check_go, "ジェネリクス（型パラメータ）または具体的なインターフェースで置き換えてください。"),
    ".rs": (_check_rust, "具体的なトレイト境界またはジェネリクスで置き換えてください。"),
}


def main() -> None:
    data = json.load(sys.stdin)
    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    ext = ""
    for e in _CHECKERS:
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

    checker, suggestion = _CHECKERS[ext]
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
