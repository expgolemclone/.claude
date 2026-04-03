#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block Python functions missing type annotations."""

import json
import re
import sys

_COMMENT_RE = re.compile(r"^\s*#")
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(->.*)?:")
_DEF_HEAD_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")
_SELF_CLS_RE = re.compile(r"^(self|cls)$")
_RETURN_EXEMPT = {"__init__", "__new__"}


def _params_missing_annotation(params_str: str) -> list[str]:
    """Return parameter names that lack type annotations."""
    if not params_str.strip():
        return []

    missing: list[str] = []
    depth = 0
    current = ""

    for ch in params_str:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            _check_param(current.strip(), missing)
            current = ""
        else:
            current += ch

    if current.strip():
        _check_param(current.strip(), missing)

    return missing


def _check_param(param: str, missing: list[str]) -> None:
    if not param or param.startswith("*"):
        if param.startswith("**"):
            name = param.lstrip("*").split("=")[0].split(":")[0].strip()
            if name and ":" not in param:
                missing.append(param)
        elif param.startswith("*") and param != "*":
            name = param.lstrip("*").split("=")[0].split(":")[0].strip()
            if name and ":" not in param:
                missing.append(param)
        return

    name = param.split("=")[0].split(":")[0].strip()
    if _SELF_CLS_RE.match(name):
        return

    if ":" not in param:
        missing.append(name)


def _check_def(func_name: str, params_str: str, return_annotation: str | None) -> str | None:
    missing: list[str] = _params_missing_annotation(params_str)
    if missing:
        return f"関数 `{func_name}` の引数 {', '.join(missing)} に型アノテーションがありません。"
    if not return_annotation and func_name not in _RETURN_EXEMPT:
        return f"関数 `{func_name}` に戻り値の型アノテーション（-> ...）がありません。"
    return None


def _check_python(text: str) -> str | None:
    lines: list[str] = text.splitlines()
    i: int = 0
    while i < len(lines):
        line: str = lines[i]
        if _COMMENT_RE.match(line):
            i += 1
            continue

        m = _DEF_RE.match(line)
        if m:
            err: str | None = _check_def(m.group(1), m.group(2), m.group(3))
            if err:
                return err
            i += 1
            continue

        head = _DEF_HEAD_RE.match(line)
        if head:
            combined: str = line
            depth: int = line.count("(") - line.count(")")
            while depth > 0 and i + 1 < len(lines):
                i += 1
                combined += " " + lines[i].strip()
                depth += lines[i].count("(") - lines[i].count(")")

            m = _DEF_RE.match(combined)
            if m:
                err = _check_def(m.group(1), m.group(2), m.group(3))
                if err:
                    return err

        i += 1

    return None


def main() -> None:
    data = json.load(sys.stdin)
    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not file_path.endswith(".py"):
        return

    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        return

    if not content:
        return

    reason = _check_python(content)
    if reason:
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "型アノテーションが不足しています（config: explicit_annotations = true）。\n"
                    f"{reason}"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
