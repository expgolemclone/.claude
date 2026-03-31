#!/usr/bin/env python3
"""PreToolUse hook: block edits to protected lines in configuration.nix."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nix_protected import PROTECTED_PATTERNS

CONFIG_FILENAME = "configuration.nix"


def is_config_file(file_path: str) -> bool:
    return file_path.endswith(CONFIG_FILENAME)


def has_protected_pattern(text: str) -> list[str]:
    matched = []
    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, text):
            matched.append(pattern)
    return matched


def check_edit(tool_input: dict) -> str | None:
    file_path = tool_input.get("file_path", "")
    if not is_config_file(file_path):
        return None

    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    old_matches = has_protected_pattern(old_string)
    if not old_matches:
        return None

    for pattern in old_matches:
        old_lines = [ln for ln in old_string.splitlines() if re.search(pattern, ln)]
        new_lines = [ln for ln in new_string.splitlines() if re.search(pattern, ln)]
        if old_lines != new_lines:
            return f"保護対象の設定行を変更しようとしています: {pattern}"

    return None


def check_write(tool_input: dict) -> str | None:
    file_path = tool_input.get("file_path", "")
    if not is_config_file(file_path):
        return None

    path = Path(file_path)
    if not path.exists():
        return None

    current_content = path.read_text()
    new_content = tool_input.get("content", "")

    for pattern in PROTECTED_PATTERNS:
        current_lines = [ln.strip() for ln in current_content.splitlines() if re.search(pattern, ln)]
        new_lines = [ln.strip() for ln in new_content.splitlines() if re.search(pattern, ln)]
        if current_lines and current_lines != new_lines:
            return f"保護対象の設定行が変更または削除されます: {pattern}"

    return None


def main() -> None:
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool_name == "Edit":
        reason = check_edit(tool_input)
    elif tool_name == "Write":
        reason = check_write(tool_input)
    else:
        return

    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
