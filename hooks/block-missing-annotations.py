#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write): block Python functions missing type annotations."""

import json
import re
import sys

_COMMENT_RE = re.compile(r"^\s*#")
_DEF_HEAD_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")
_RETURN_ARROW_RE = re.compile(r"\s*->")
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


def _has_annotation(param: str) -> bool:
    """depth-0 の `:` が `=` より前にあれば型アノテーション有りと判定。"""
    depth: int = 0
    for ch in param:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "=" and depth == 0:
            return False
        elif ch == ":" and depth == 0:
            return True
    return False


def _param_name(param: str) -> str:
    """パラメータ文字列から名前部分のみを抽出。"""
    return param.lstrip("*").split("=")[0].split(":")[0].strip()


def _check_param(param: str, missing: list[str]) -> None:
    if not param or param in ("/", "*"):
        return

    if param.startswith("*"):
        name: str = _param_name(param)
        if name and not _has_annotation(param):
            missing.append(name)
        return

    name = _param_name(param)
    if _SELF_CLS_RE.match(name):
        return

    if not _has_annotation(param):
        missing.append(name)


def _check_def(func_name: str, params_str: str, return_annotation: str | None) -> str | None:
    missing: list[str] = _params_missing_annotation(params_str)
    if missing:
        return f"関数 `{func_name}` の引数 {', '.join(missing)} に型アノテーションがありません。"
    if not return_annotation and func_name not in _RETURN_EXEMPT:
        return f"関数 `{func_name}` に戻り値の型アノテーション（-> ...）がありません。"
    return None


def _extract_def(lines: list[str], start: int) -> tuple[str, str, str | None, int]:
    """def 文から (関数名, パラメータ文字列, 戻り値アノテーション, 終了行) を抽出。"""
    combined: str = lines[start]
    i: int = start
    depth: int = combined.count("(") - combined.count(")")
    while depth > 0 and i + 1 < len(lines):
        i += 1
        combined += " " + lines[i].strip()
        depth += lines[i].count("(") - lines[i].count(")")

    head: re.Match[str] | None = _DEF_HEAD_RE.match(combined)
    func_name: str = head.group(1) if head else ""

    # depth-aware で最外の ( に対応する ) を探す
    paren_start: int = combined.index("(")
    paren_depth: int = 0
    paren_end: int = paren_start
    for j in range(paren_start, len(combined)):
        if combined[j] == "(":
            paren_depth += 1
        elif combined[j] == ")":
            paren_depth -= 1
            if paren_depth == 0:
                paren_end = j
                break

    params_str: str = combined[paren_start + 1 : paren_end]
    after_paren: str = combined[paren_end + 1 :]
    return_annotation: str | None = after_paren.strip().rstrip(":").strip() or None
    if return_annotation and not _RETURN_ARROW_RE.match(return_annotation):
        return_annotation = None

    return func_name, params_str, return_annotation, i


def _check_python(text: str) -> str | None:
    lines: list[str] = text.splitlines()
    i: int = 0
    while i < len(lines):
        line: str = lines[i]
        if _COMMENT_RE.match(line):
            i += 1
            continue

        if _DEF_HEAD_RE.match(line):
            func_name: str
            params_str: str
            return_annotation: str | None
            func_name, params_str, return_annotation, i = _extract_def(lines, i)
            err: str | None = _check_def(func_name, params_str, return_annotation)
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
