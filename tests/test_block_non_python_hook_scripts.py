#!/usr/bin/env python3
"""Tests for block-non-python-hook-scripts.py hook."""

import json
import subprocess
import sys

HOOK = "/home/exp/.claude/hooks/block-non-python-hook-scripts.py"


def run_hook(tool_input: dict) -> dict | None:
    payload = json.dumps({"tool_input": tool_input})
    result = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test(name: str, tool_input: dict, *, should_block: bool) -> bool:
    result = run_hook(tool_input)
    blocked = result is not None and result.get("decision") == "block"
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- should block (non-Python in hooks/) ---")
    results.append(test(
        ".sh in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.sh"},
        should_block=True,
    ))
    results.append(test(
        ".js in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.js"},
        should_block=True,
    ))
    results.append(test(
        ".ts in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.ts"},
        should_block=True,
    ))
    results.append(test(
        ".bash in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.bash"},
        should_block=True,
    ))
    results.append(test(
        ".rb in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.rb"},
        should_block=True,
    ))

    print("\n--- should allow ---")
    results.append(test(
        ".py in hooks/",
        {"file_path": "/home/exp/.claude/hooks/myhook.py"},
        should_block=False,
    ))
    results.append(test(
        ".sh outside hooks/",
        {"file_path": "/home/exp/project/script.sh"},
        should_block=False,
    ))
    results.append(test(
        ".toml in hooks/ (not in blocked list)",
        {"file_path": "/home/exp/.claude/hooks/config.toml"},
        should_block=False,
    ))
    results.append(test(
        "no file_path",
        {},
        should_block=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
