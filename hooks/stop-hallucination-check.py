#!/usr/bin/env python3
"""Stop hook: warn when responding without primary source verification."""

import json
import sys

MIN_RESPONSE_LENGTH = 200


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    last_msg = data.get("last_assistant_message", "")
    if len(last_msg) < MIN_RESPONSE_LENGTH:
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    used_any_tool = False

    try:
        with open(transcript_path) as f:
            lines = f.readlines()

        # Find the last user message line in the transcript
        # Transcript format: entry["type"] == "user" marks a user message
        last_user_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            try:
                entry = json.loads(lines[i])
                if entry.get("type") == "user":
                    last_user_idx = i
                    break
            except json.JSONDecodeError:
                continue

        if last_user_idx < 0:
            return

        # Check for tool usage after the last user message
        # Tool usage is recorded as {"type": "tool_use", "name": "ToolName"}
        # within entry["message"]["content"][]
        for line in lines[last_user_idx + 1 :]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = entry.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    used_any_tool = True
                    break
            if used_any_tool:
                break

    except (OSError, json.JSONDecodeError):
        return

    if used_any_tool:
        return

    json.dump(
        {
            "decision": "block",
            "reason": (
                "This response lacks primary source verification.\n"
                "If answering a knowledge-based question, verify with WebSearch or "
                "WebFetch before responding.\n"
                "If responding to a coding task, you may proceed without verification."
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
