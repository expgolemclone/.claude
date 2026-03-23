#!/usr/bin/env python3
"""Tests for block-git-add-force-staging.py hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR

HOOK = str(HOOKS_DIR / "block-git-add-force-staging.py")


def run_hook(command: str) -> dict | None:
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test(name: str, command: str, *, should_block: bool) -> bool:
    result = run_hook(command)
    blocked = result is not None and result.get("decision") == "block"
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- should block ---")
    results.append(test(
        "git add -f",
        "git add -f .",
        should_block=True,
    ))
    results.append(test(
        "git add --force",
        "git add --force somefile.txt",
        should_block=True,
    ))
    results.append(test(
        "git add -f with path",
        "git add -f node_modules/",
        should_block=True,
    ))

    print("\n--- should allow ---")
    results.append(test(
        "normal git add",
        "git add .",
        should_block=False,
    ))
    results.append(test(
        "git add specific file",
        "git add main.py",
        should_block=False,
    ))
    results.append(test(
        "not a git command",
        "echo hello",
        should_block=False,
    ))
    results.append(test(
        "-f inside quotes (not real flag)",
        'git commit -m "add -f feature flag"',
        should_block=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
