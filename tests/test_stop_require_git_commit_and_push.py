#!/usr/bin/env python3
"""Tests for stop-require-git-commit-and-push.py hook."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR

HOOK = str(HOOKS_DIR / "stop-require-git-commit-and-push.py")


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
        if result:
            print(f"         reason: {result.get('reason', '')[:100]}")
    return ok


def main() -> None:
    results: list[bool] = []

    repo_dir = str(HOOKS_DIR)
    non_git_dir = tempfile.gettempdir()

    print("--- early return conditions ---")
    results.append(test(
        "stop_hook_active -> skip",
        {"stop_hook_active": True, "cwd": repo_dir},
        should_block=False,
    ))
    results.append(test(
        "permission_mode=plan -> skip",
        {"permission_mode": "plan", "cwd": repo_dir},
        should_block=False,
    ))

    print("\n--- in a git repo with changes ---")
    # This test runs in the current repo which has uncommitted changes per git status
    results.append(test(
        "cwd with uncommitted changes -> block",
        {"cwd": repo_dir},
        should_block=True,
    ))

    print("\n--- not a git repo ---")
    results.append(test(
        "cwd=tempdir (not a git repo) -> skip",
        {"cwd": non_git_dir},
        should_block=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
