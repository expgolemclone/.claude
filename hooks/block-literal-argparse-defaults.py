#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): block add_argument(default=<numeric literal>).

Numeric defaults in argparse should come from a config dict, not be
hardcoded as int/float literals.  Suppress per-line with
``# noqa: literal-default``.
"""

import ast
import json
import os
import sys


def _find_violations(source: str, lines: list[str]) -> list[tuple[int, object]]:
    """Return (lineno, value) for each add_argument default=<int|float>."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    violations: list[tuple[int, object]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
        ):
            continue
        for kw in node.keywords:
            if kw.arg != "default":
                continue
            if not isinstance(kw.value, ast.Constant):
                continue
            if not isinstance(kw.value.value, (int, float)):
                continue
            line = lines[kw.value.lineno - 1]
            if "# noqa: literal-default" in line:
                continue
            violations.append((kw.value.lineno, kw.value.value))
    return violations


def main() -> None:
    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    if "/tests/" in file_path or os.path.basename(file_path).startswith("test_"):
        return

    if not os.path.isfile(file_path):
        return

    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    if "add_argument" not in source:
        return

    lines = source.splitlines()
    violations = _find_violations(source, lines)
    if not violations:
        return

    details = "\n".join(f"  L{lineno}: default={value}" for lineno, value in violations)
    json.dump(
        {
            "decision": "stop",
            "reason": (
                f"{os.path.basename(file_path)} に add_argument(default=<数値リテラル>) があります。\n"
                f"{details}\n"
                "設定ファイルの定数を参照してください (# noqa: literal-default で除外可)。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
