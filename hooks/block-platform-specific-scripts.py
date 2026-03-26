#!/usr/bin/env python3
"""PreToolUse hook (Write|Bash): block platform-specific script creation.

.sh/.bash/.zsh/.csh/.tcsh/.fish/.ksh → Windows非対応のためブロック
.ps1/.psm1/.psd1/.bat/.cmd/.vbs/.vbe/.wsf/.wsh → Linux非対応のためブロック
いずれも .py への変更を促す。

Edit（既存ファイル編集）は許可。Write（新規作成）とBash（リダイレクト等）をブロック。
"""

import json
import os
import re
import sys

UNIX_ONLY_EXTENSIONS = {".sh", ".bash", ".zsh", ".csh", ".tcsh", ".fish", ".ksh"}
WINDOWS_ONLY_EXTENSIONS = {".ps1", ".psm1", ".psd1", ".bat", ".cmd", ".vbs", ".vbe", ".wsf", ".wsh"}
ALL_BLOCKED = UNIX_ONLY_EXTENSIONS | WINDOWS_ONLY_EXTENSIONS

# Bash: ファイル作成を示すパターンから出力先ファイル名を抽出
_REDIRECT_RE = re.compile(r">{1,2}\s*([\"']?)(\S+)\1")
_TOUCH_RE = re.compile(r"\btouch\s+(?:-\S+\s+)*([\"']?)(\S+)\1")
_TEE_RE = re.compile(r"\btee\s+(?:-\S+\s+)*([\"']?)(\S+)\1")


def classify(ext: str) -> str | None:
    """Return block reason or None if allowed."""
    if ext in UNIX_ONLY_EXTENSIONS:
        return f"それはWindowsでは使えません。.pyにしてください。（{ext}）"
    if ext in WINDOWS_ONLY_EXTENSIONS:
        return f"それはLinuxでは使えません。.pyにしてください。（{ext}）"
    return None


def check_file_path(file_path: str) -> None:
    """Block Write tool targeting a platform-specific extension."""
    ext = os.path.splitext(file_path)[1].lower()
    reason = classify(ext)
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


def extract_output_files(command: str) -> list[str]:
    """Extract potential output file paths from a bash command."""
    files: list[str] = []
    for pattern in (_REDIRECT_RE, _TOUCH_RE, _TEE_RE):
        for match in pattern.finditer(command):
            files.append(match.group(2))
    return files


def check_command(command: str) -> None:
    """Block Bash commands that create platform-specific scripts."""
    for filepath in extract_output_files(command):
        ext = os.path.splitext(filepath)[1].lower()
        reason = classify(ext)
        if reason:
            json.dump({"decision": "block", "reason": reason}, sys.stdout)
            return


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})

    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if file_path:
        check_file_path(file_path)
        return

    command = tool_input.get("command", "")
    if command:
        check_command(command)


if __name__ == "__main__":
    main()
