#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block dependency versions without upper bounds."""

import json
import os
import re
import sys

_CARGO_WILDCARD_RE = re.compile(r"""['"](\s*\*\s*)['"]""")

_FILE_CHECKERS: dict[str, str] = {
    "pyproject.toml": "pyproject",
    "Cargo.toml": "cargo",
    "package.json": "package_json",
}


def _check_pyproject(content: str) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "requires-python" in stripped:
            continue
        if ">=" in stripped and "<" not in stripped and "~=" not in stripped:
            if re.search(r""">=\s*[\d]""", stripped):
                return True
    return False


def _check_cargo(content: str) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _CARGO_WILDCARD_RE.search(stripped):
            return True
        if ">=" in stripped and "<" not in stripped:
            if re.search(r""">=\s*[\d]""", stripped):
                return True
    return False


def _check_package_json(content: str) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        if ">=" in stripped and "<" not in stripped:
            if re.search(r""">=\s*[\d]""", stripped):
                return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path:
        return

    basename = os.path.basename(file_path)
    checker_key = _FILE_CHECKERS.get(basename)
    if not checker_key:
        return

    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        return

    if not content:
        return

    if checker_key == "pyproject":
        found = _check_pyproject(content)
    elif checker_key == "cargo":
        found = _check_cargo(content)
    elif checker_key == "package_json":
        found = _check_package_json(content)
    else:
        return

    if found:
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "バージョン上限のない依存指定は禁止です（config: upper_bound_required = true）。\n"
                    ">= のみではなく、上限も指定してください（例: >=1.0,<2 / ~=1.0 / ^1.0）。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
