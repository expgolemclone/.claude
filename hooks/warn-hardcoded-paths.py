#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): warn when .py files contain hardcoded absolute paths.

rules/common.toml の hardcoded_paths_prohibited = true を実行時に検証する。
ハードコードされた絶対パスを検出したら stop で警告し、パス定数の集約を促す。
"""

import json
import os
import re
import sys

# Unix系の絶対パスプレフィックス
_UNIX_PREFIXES = ("/home/", "/usr/", "/etc/", "/var/", "/opt/", "/tmp/")

# Windowsドライブレター（C:\, D:/, etc.）
_WIN_DRIVE_RE = re.compile(r"[A-Za-z]:[/\\]")

# 除外パターン
_SHEBANG_RE = re.compile(r"^#!")
_COMMENT_RE = re.compile(r"^\s*#")
_IMPORT_RE = re.compile(r"^\s*(import|from)\s+")
_DYNAMIC_PATH_RE = re.compile(r"__file__|Path\s*\(\s*__file__\s*\)")


def _is_excluded_line(line: str) -> bool:
    """除外すべき行かどうかを判定する。"""
    if _SHEBANG_RE.match(line):
        return True
    if _COMMENT_RE.match(line):
        return True
    if _IMPORT_RE.match(line):
        return True
    if _DYNAMIC_PATH_RE.search(line):
        return True
    return False


def _has_hardcoded_path(line: str) -> str | None:
    """行にハードコードされた絶対パスがあればそのパス文字列を返す。"""
    for prefix in _UNIX_PREFIXES:
        if prefix in line:
            return prefix
    if _WIN_DRIVE_RE.search(line):
        match = _WIN_DRIVE_RE.search(line)
        if match:
            return match.group()
    return None


def scan_file(file_path: str) -> list[tuple[int, str, str]]:
    """ファイルをスキャンしてハードコードパスを含む行を返す。

    Returns:
        list of (line_number, line_content, detected_path)
    """
    results: list[tuple[int, str, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                if _is_excluded_line(line):
                    continue
                path = _has_hardcoded_path(line)
                if path:
                    results.append((i, line.rstrip(), path))
    except (OSError, UnicodeDecodeError):
        pass
    return results


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    hits = scan_file(file_path)
    if not hits:
        return

    lines_info = "\n".join(f"  L{num}: {content}" for num, content, _ in hits[:5])
    if len(hits) > 5:
        lines_info += f"\n  ... 他 {len(hits) - 5} 件"

    json.dump(
        {
            "decision": "stop",
            "reason": (
                "ハードコードされた絶対パスが検出されました。\n"
                f"{lines_info}\n"
                "パス定数は設定ファイルに集約してください（rules/common.toml: hardcoded_paths_prohibited）。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
