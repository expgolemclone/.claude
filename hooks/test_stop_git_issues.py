#!/usr/bin/env python3
"""Tests for stop-git-issues.py hook."""

import json
import subprocess
import sys

HOOK = "/home/exp/.claude/hooks/stop-git-issues.py"


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


def test(name: str, data: dict, *, should_block: bool | None) -> bool:
    result = run_hook(data)
    blocked = result is not None and result.get("decision") == "block"
    if should_block is None:
        # We don't know the expected result (depends on whether gh has issues)
        print(f"  [INFO] {name} -> {'block' if blocked else 'allow'}")
        return True
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- early return conditions ---")
    results.append(test(
        "stop_hook_active -> skip",
        {"stop_hook_active": True, "cwd": "/home/exp/.claude/hooks"},
        should_block=False,
    ))

    print("\n--- not a git repo ---")
    results.append(test(
        "cwd=/tmp (not a git repo) -> skip",
        {"cwd": "/tmp"},
        should_block=False,
    ))

    print("\n--- in a git repo (result depends on open issues) ---")
    results.append(test(
        "cwd in repo -> depends on gh issues",
        {"cwd": "/home/exp/.claude/hooks"},
        should_block=None,  # cannot predict
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
