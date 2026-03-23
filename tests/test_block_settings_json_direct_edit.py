#!/usr/bin/env python3
"""Tests for block-settings-json-direct-edit.py hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR, SETTINGS_JSON

HOOK = str(HOOKS_DIR / "block-settings-json-direct-edit.py")


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

    settings_path = str(SETTINGS_JSON)

    print("--- should block ---")
    results.append(test(
        "direct path to settings.json",
        {"file_path": settings_path},
        should_block=True,
    ))
    results.append(test(
        "path with forward slashes to settings.json",
        {"file_path": settings_path.replace("\\", "/")},
        should_block=True,
    ))

    print("\n--- should allow ---")
    results.append(test(
        "other json file",
        {"file_path": str(SETTINGS_JSON.parent / "other.json")},
        should_block=False,
    ))
    results.append(test(
        "settings.json in different directory",
        {"file_path": "/tmp/project/settings.json"},
        should_block=False,
    ))
    results.append(test(
        "empty file_path",
        {"file_path": ""},
        should_block=False,
    ))
    results.append(test(
        "no file_path key",
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
