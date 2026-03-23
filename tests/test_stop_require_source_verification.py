#!/usr/bin/env python3
"""Tests for stop-require-source-verification.py hook."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR

HOOK = str(HOOKS_DIR / "stop-require-source-verification.py")


def run_hook(data: dict) -> dict | None:
    payload = json.dumps(data)
    result = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test(name: str, data: dict, *, should_block: bool) -> bool:
    result = run_hook(data)
    blocked = result is not None and result.get("decision") == "block"
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
    return ok


def make_transcript(lines: list[str]) -> str:
    """Write transcript lines to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return path


def main() -> None:
    results: list[bool] = []

    print("--- early return conditions ---")
    results.append(test(
        "stop_hook_active -> skip",
        {"stop_hook_active": True, "last_assistant_message": "x" * 300},
        should_block=False,
    ))
    results.append(test(
        "short response -> skip",
        {"last_assistant_message": "OK"},
        should_block=False,
    ))
    results.append(test(
        "no transcript_path -> skip",
        {"last_assistant_message": "x" * 300},
        should_block=False,
    ))
    results.append(test(
        "empty transcript_path -> skip",
        {"last_assistant_message": "x" * 300, "transcript_path": ""},
        should_block=False,
    ))

    print("\n--- long response without tool use -> block ---")
    transcript = make_transcript([
        json.dumps({"type": "user", "message": {"content": "What is NixOS?"}}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 300}]}}),
    ])
    try:
        results.append(test(
            "long response, no tool use -> block",
            {
                "last_assistant_message": "x" * 300,
                "transcript_path": transcript,
            },
            should_block=True,
        ))
    finally:
        os.unlink(transcript)

    print("\n--- long response with tool use -> allow ---")
    transcript = make_transcript([
        json.dumps({"type": "user", "message": {"content": "What is NixOS?"}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "WebSearch"},
            {"type": "text", "text": "x" * 300},
        ]}}),
    ])
    try:
        results.append(test(
            "long response, with tool use -> allow",
            {
                "last_assistant_message": "x" * 300,
                "transcript_path": transcript,
            },
            should_block=False,
        ))
    finally:
        os.unlink(transcript)

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
