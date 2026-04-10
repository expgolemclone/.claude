#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): block numeric literal keyword arguments.

Numeric values passed as keyword arguments in function calls should come
from config or named constants, not be hardcoded as int/float literals.
Suppress per-line with ``# noqa: magic-number``.
"""

import ast
import json
import os
import sys

_SAFE_VALUES: set[int | float] = {0, 1, -1, 0.0, 1.0}

_ALLOWLISTED_CALLS: dict[str, set[str]] = {
    "range": {"start", "stop", "step"},
    "enumerate": {"start"},
    "round": {"ndigits"},
    "int": {"base"},
    "slice": {"start", "stop", "step"},
    "exit": {"code"},
    "print": {"end", "sep", "flush"},
    "open": {"buffering"},
    "isinstance": set(),
    "issubclass": set(),
    "len": set(),
    "type": set(),
    "super": set(),
}


def _get_func_name(func: ast.expr) -> str:
    """Extract the function name from a Call node."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _find_violations(source: str, lines: list[str]) -> list[tuple[int, str, object]]:
    """Return (lineno, keyword, value) for each numeric literal kwarg."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    violations: list[tuple[int, str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _get_func_name(node.func)
        allowed_kwargs = _ALLOWLISTED_CALLS.get(func_name)
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if not isinstance(kw.value, ast.Constant):
                continue
            if not isinstance(kw.value.value, (int, float)):
                continue
            if isinstance(kw.value.value, bool):
                continue
            if kw.value.value in _SAFE_VALUES:
                continue
            if allowed_kwargs is not None and (
                not allowed_kwargs or kw.arg in allowed_kwargs
            ):
                continue
            line = lines[kw.value.lineno - 1]
            if "# noqa: magic-number" in line:
                continue
            violations.append((kw.value.lineno, kw.arg, kw.value.value))
    return violations


def main() -> None:
    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    normalized = file_path.replace("\\", "/")
    if "/tests/" in normalized or os.path.basename(file_path).startswith("test_"):
        return

    if not os.path.isfile(file_path):
        return

    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()
    violations = _find_violations(source, lines)
    if not violations:
        return

    details = "\n".join(
        f"  L{lineno}: {kwarg}={value}" for lineno, kwarg, value in violations
    )
    json.dump(
        {
            "decision": "stop",
            "reason": (
                f"{os.path.basename(file_path)} にマジックナンバーのキーワード引数があります。\n"
                f"{details}\n"
                "設定ファイルまたは名前付き定数を使用してください (# noqa: magic-number で除外可)。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
