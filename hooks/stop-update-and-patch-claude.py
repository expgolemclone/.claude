#!/usr/bin/env python3
"""Stop hook: セッション終了時に claude-code をアップデートしマスコットパッチを適用する."""

import json
import subprocess
import sys
from pathlib import Path

PATCH_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "patch-clawd-mascot.py"
NOTIFY_MARKER = "パッチ適用"


def _update_claude_code() -> str | None:
    """npm で claude-code を最新版にアップデートし、出力を返す（変更なしは None）."""
    cmd = ["npm", "install", "-g", "@anthropic-ai/claude-code@latest"]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if result.returncode != 0:
        return f"update failed: {result.stderr.strip()}"

    output = result.stdout.strip()
    return output if output else None


def _patch_mascot() -> str | None:
    """マスコット非表示パッチを適用し、出力を返す（既に済みは None）."""
    result = subprocess.run(
        [sys.executable, str(PATCH_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = result.stdout.strip()
    return output if NOTIFY_MARKER in output else None


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("permission_mode") == "plan":
        return

    messages: list[str] = []

    update_msg = _update_claude_code()
    if update_msg:
        messages.append(f"[update] {update_msg}")

    patch_msg = _patch_mascot()
    if patch_msg:
        messages.append(f"[patch] {patch_msg}")

    if messages:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": "\n".join(messages),
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
