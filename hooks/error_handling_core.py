"""Shared detection logic for error_handling rules (no_bare_except, no_silent_swallow).

AST-based checker that detects two mechanically enforceable rules:
- no_bare_except: except / except Exception / except BaseException
- no_silent_swallow: except handler with no re-raise and no notification
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

_BROAD_EXCEPT_NAMES: frozenset[str] = frozenset({"Exception", "BaseException"})

_NOTIFICATION_ATTRS: frozenset[str] = frozenset({
    "error", "warning", "warn", "info", "debug",
    "critical", "exception", "fatal", "log",
})
_NOTIFICATION_NAMES: frozenset[str] = frozenset({"print", "log"})


@dataclass(frozen=True)
class Violation:
    line: int
    col: int
    rule: str
    snippet: str

    def __str__(self) -> str:
        return f"L{self.line}:{self.col} [{self.rule}] {self.snippet}"


def _is_broad_except(exc_type: ast.expr | None) -> bool:
    if exc_type is None:
        return True
    if isinstance(exc_type, ast.Name):
        return exc_type.id in _BROAD_EXCEPT_NAMES
    if isinstance(exc_type, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id in _BROAD_EXCEPT_NAMES
            for elt in exc_type.elts
        )
    return False


def _has_raise(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def _has_notification_call(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in _NOTIFICATION_NAMES:
                return True
            if isinstance(func, ast.Attribute) and func.attr in _NOTIFICATION_ATTRS:
                return True
    return False


def _is_trivial_value(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return not node.elts
    return isinstance(node, ast.Dict) and not node.keys


def _is_silent_body(body: list[ast.stmt]) -> bool:
    if not body or _has_raise(body) or _has_notification_call(body):
        return False
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Return):
        return stmt.value is None or _is_trivial_value(stmt.value)
    if isinstance(stmt, ast.Assign):
        return _is_trivial_value(stmt.value)
    return False


def check_python(source: str) -> list[Violation]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        snippet = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        if _is_broad_except(node.type):
            violations.append(Violation(node.lineno, node.col_offset, "no_bare_except", snippet))
        if _is_silent_body(node.body):
            violations.append(Violation(node.lineno, node.col_offset, "no_silent_swallow", snippet))
    return violations
