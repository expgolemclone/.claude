#!/usr/bin/env python3
"""Stop hook: prompt to create or update ARCHITECTURE.md after file edits."""

import json
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write"}
ARCHITECTURE_FILENAME = "ARCHITECTURE.md"


def _scan_transcript(transcript_path: str) -> tuple[bool, bool]:
    """Return (edited_non_architecture, edited_architecture) from transcript."""
    edited_non_architecture = False
    edited_architecture = False

    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return False, False

    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") not in EDIT_TOOLS:
                continue

            file_path: str = block.get("input", {}).get("file_path", "")
            if not file_path:
                continue

            if Path(file_path).name == ARCHITECTURE_FILENAME:
                edited_architecture = True
            else:
                edited_non_architecture = True

    return edited_non_architecture, edited_architecture


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    edited_files, edited_arch = _scan_transcript(transcript_path)

    if not edited_files:
        return

    cwd = data.get("cwd", "")
    arch_exists = (Path(cwd) / ARCHITECTURE_FILENAME).is_file() if cwd else False

    if not arch_exists:
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "ARCHITECTURE.md が存在しません。\n"
                    "ファイル構成の変更を反映するため作成してください。"
                ),
            },
            sys.stdout,
        )
        return

    if not edited_arch:
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "ファイルを編集しましたが ARCHITECTURE.md を更新していません。\n"
                    "変更内容を反映してください。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
