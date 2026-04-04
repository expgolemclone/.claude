#!/usr/bin/env python3
"""Stop hook: block when responding without WebSearch/WebFetch verification."""

import json
import sys

SEARCH_TOOLS = {"WebSearch", "WebFetch"}
CODING_TOOLS = {"Edit", "Write", "Bash", "Read", "Grep", "Glob", "NotebookEdit"}


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    used_search = False
    used_coding_tool = False

    try:
        with open(transcript_path) as f:
            lines = f.readlines()

        # Find the last *real* user message (not a tool_result relay).
        last_real_user_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            try:
                entry = json.loads(lines[i])
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "user":
                continue
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list) and all(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in content
                if isinstance(b, dict)
            ):
                continue
            last_real_user_idx = i
            break

        if last_real_user_idx < 0:
            return

        # Check for WebSearch/WebFetch tool_use after the last real user message
        for line in lines[last_real_user_idx + 1 :]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = entry.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_name: str = block.get("name", "")
                    if tool_name in SEARCH_TOOLS:
                        used_search = True
                    if tool_name in CODING_TOOLS:
                        used_coding_tool = True
            if used_search:
                break

    except (OSError, json.JSONDecodeError):
        return

    if used_search or used_coding_tool:
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
