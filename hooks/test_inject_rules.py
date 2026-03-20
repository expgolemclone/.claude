#!/usr/bin/env python3
"""Tests for inject-rules.py hook."""

import json
import subprocess
import sys

HOOK = "/home/exp/.claude/hooks/inject-rules.py"


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


def test(name: str, tool_input: dict, *, should_inject: bool) -> bool:
    result = run_hook(tool_input)
    injected = result is not None and "additionalContext" in result.get("hookSpecificOutput", {})
    ok = injected == should_inject
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'inject' if should_inject else 'none'}, got={'inject' if injected else 'none'}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- Edit/Write: file extension rules ---")
    results.append(test(
        ".py file injects py.toml",
        {"file_path": "/home/exp/project/main.py"},
        should_inject=True,
    ))
    results.append(test(
        ".md file injects md.toml (+ mmd.toml)",
        {"file_path": "/home/exp/docs/README.md"},
        should_inject=True,
    ))
    results.append(test(
        ".rs file injects rs.toml",
        {"file_path": "/home/exp/project/main.rs"},
        should_inject=True,
    ))
    results.append(test(
        ".cs file -> no injection (cs.toml is empty)",
        {"file_path": "/home/exp/project/Program.cs"},
        should_inject=False,
    ))

    print("\n--- Edit/Write: no injection ---")
    results.append(test(
        "no extension -> no injection",
        {"file_path": "/home/exp/project/Makefile"},
        should_inject=False,
    ))
    results.append(test(
        "unknown extension -> no injection",
        {"file_path": "/home/exp/project/data.xyz"},
        should_inject=False,
    ))
    results.append(test(
        "empty file_path -> no injection",
        {"file_path": ""},
        should_inject=False,
    ))
    results.append(test(
        "no file_path key -> no injection",
        {"command": "echo hello"},
        should_inject=False,
    ))

    print("\n--- Bash: git command rules ---")
    results.append(test(
        "git commit injects git.toml",
        {"command": "git commit -m 'test'"},
        should_inject=True,
    ))
    results.append(test(
        "git push injects git.toml",
        {"command": "git push origin main"},
        should_inject=True,
    ))
    results.append(test(
        "non-git command -> no injection",
        {"command": "echo hello"},
        should_inject=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
