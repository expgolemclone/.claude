"""Shared detection logic for Any type usage in Python, Go, and Rust."""

import re
from typing import Callable

_PY_IMPORT_ANY_RE = re.compile(r"from\s+typing\b.*\bAny\b")
_PY_QUALIFIED_ANY_RE = re.compile(r"\btyping\.Any\b")
_PY_BARE_ANY_RE = re.compile(r"\bAny\b")
_PY_COMMENT_RE = re.compile(r"^\s*#")
_PY_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"|' + r"'(?:[^'\\]|\\.)*'")

_GO_COMMENT_RE = re.compile(r"^\s*//")
_GO_IMPORT_RE = re.compile(r"^\s*import\s")
_GO_INTERFACE_EMPTY_RE = re.compile(r"\binterface\s*\{\s*\}")
_GO_ANY_TYPE_RE = re.compile(r"\bany\b")
_GO_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"|`[^`]*`')

_RS_COMMENT_RE = re.compile(r"^\s*//")
_RS_USE_ANY_RE = re.compile(r"\buse\s+std::any::Any\b")
_RS_DYN_ANY_RE = re.compile(r"\bdyn\s+Any\b")
_RS_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def check_python(text: str) -> bool:
    for line in text.splitlines():
        if _PY_COMMENT_RE.match(line):
            continue
        stripped = _PY_STRING_RE.sub('""', line)
        if _PY_IMPORT_ANY_RE.search(stripped):
            return True
        if _PY_QUALIFIED_ANY_RE.search(stripped):
            return True
        if _PY_BARE_ANY_RE.search(stripped):
            return True
    return False


def check_go(text: str) -> bool:
    for line in text.splitlines():
        if _GO_COMMENT_RE.match(line):
            continue
        if _GO_IMPORT_RE.match(line):
            continue
        stripped = _GO_STRING_RE.sub('""', line)
        if _GO_INTERFACE_EMPTY_RE.search(stripped):
            return True
        if _GO_ANY_TYPE_RE.search(stripped):
            return True
    return False


def check_rust(text: str) -> bool:
    for line in text.splitlines():
        if _RS_COMMENT_RE.match(line):
            continue
        stripped = _RS_STRING_RE.sub('""', line)
        if _RS_USE_ANY_RE.search(stripped):
            return True
        if _RS_DYN_ANY_RE.search(stripped):
            return True
    return False


CHECKERS: dict[str, tuple[Callable[[str], bool], str]] = {
    ".py": (check_python, "具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。"),
    ".go": (check_go, "ジェネリクス（型パラメータ）または具体的なインターフェースで置き換えてください。"),
    ".rs": (check_rust, "具体的なトレイト境界またはジェネリクスで置き換えてください。"),
}
