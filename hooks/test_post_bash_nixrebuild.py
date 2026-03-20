#!/usr/bin/env python3
"""Tests for post-bash-nixrebuild.py hook."""

import json
import subprocess
import sys

HOOK = "/home/exp/.claude/hooks/post-bash-nixrebuild.py"


def run_hook(command: str, tool_response: str = "") -> dict | None:
    payload = json.dumps({
        "tool_input": {"command": command},
        "tool_response": tool_response,
    })
    result = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test(name: str, command: str, tool_response: str, *, should_block: bool) -> bool:
    result = run_hook(command, tool_response)
    blocked = result is not None and result.get("decision") == "block"
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
        if result:
            print(f"         reason: {result.get('reason', '')[:80]}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- nixos-rebuild failure ---")
    results.append(test(
        "rebuild with error in output",
        "sudo nixos-rebuild switch --flake ~/nix-config#nixos",
        "error: attribute 'foo' missing\ntrace: ...",
        should_block=True,
    ))
    results.append(test(
        "rebuild with Failed in output",
        "sudo nixos-rebuild switch",
        "Failed to build configuration",
        should_block=True,
    ))

    print("\n--- nixos-rebuild success ---")
    results.append(test(
        "rebuild success -> check logs prompt",
        "sudo nixos-rebuild switch --flake ~/nix-config#nixos",
        "activating the configuration...\nswitching to system configuration",
        should_block=True,
    ))

    print("\n--- not nixos-rebuild ---")
    results.append(test(
        "unrelated command -> no output",
        "echo hello",
        "",
        should_block=False,
    ))
    results.append(test(
        "git command -> no output",
        "git status",
        "On branch main",
        should_block=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
