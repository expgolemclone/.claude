#!/usr/bin/env python3
"""PreToolUse hook: inject config/*.toml based on file extension or git command."""

import json
import os
import re
import sys

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".claude", "config")


def read_config(filename: str) -> str:
    try:
        with open(os.path.join(CONFIG_DIR, filename)) as f:
            return f.read().strip()
    except OSError:
        return ""


def output(ctx: str) -> None:
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}},
        sys.stdout,
    )


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})

    # Bash tool: git command -> inject git.toml
    command = tool_input.get("command", "")
    if command and re.search(r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)git\s", command):
        rules = read_config("git.toml")
        if rules:
            output(rules)
        return

    # Edit/Write tool: file extension -> inject {ext}.toml
    file_path = tool_input.get("file_path") or tool_input.get("path", "")
    if not file_path:
        return

    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if not ext:
        return

    # 共通ルールを常に注入
    common = read_config("common.toml")

    rules = read_config(ext + ".toml")

    # .md -> also inject mmd.toml
    if ext == "md":
        mmd = read_config("mmd.toml")
        if mmd:
            rules = rules + "\n\n" + mmd if rules else mmd

    # common + extension-specific を結合
    if common:
        rules = common + "\n\n" + rules if rules else common

    if rules:
        output(rules)


if __name__ == "__main__":
    main()
