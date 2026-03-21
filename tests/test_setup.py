#!/usr/bin/env python3
"""Tests for setup.py: verify both OS configs generate valid settings.json."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from setup import build_linux_config, build_windows_config


def validate_hook_entry(entry, context):
    """Validate a single hook entry has required fields."""
    assert "type" in entry, f"{context}: missing 'type'"
    assert entry["type"] == "command", f"{context}: type must be 'command', got {entry['type']}"
    assert "command" in entry, f"{context}: missing 'command'"
    assert len(entry["command"]) > 0, f"{context}: empty command"


def validate_hook_group(group, context):
    """Validate a hook group has 'hooks' list with valid entries."""
    assert "hooks" in group, f"{context}: missing 'hooks'"
    assert len(group["hooks"]) > 0, f"{context}: empty hooks list"
    for i, entry in enumerate(group["hooks"]):
        validate_hook_entry(entry, f"{context}[{i}]")


def validate_config(config, os_name):
    """Validate common structure of a config dict."""
    # Top-level keys
    assert "permissions" in config, f"{os_name}: missing permissions"
    assert "skipDangerousModePermissionPrompt" in config, f"{os_name}: missing skipDangerousModePermissionPrompt"
    assert config["skipDangerousModePermissionPrompt"] is True, f"{os_name}: skipDangerousModePermissionPrompt must be True"
    assert "hooks" in config, f"{os_name}: missing hooks"

    # Permissions
    perms = config["permissions"]
    assert "defaultMode" in perms, f"{os_name}: missing defaultMode"
    assert perms["defaultMode"] == "bypassPermissions", f"{os_name}: unexpected defaultMode"

    # Hook categories
    hooks = config["hooks"]
    for category in ("PreToolUse", "PostToolUse", "Stop"):
        assert category in hooks, f"{os_name}: missing {category}"
        assert len(hooks[category]) > 0, f"{os_name}: empty {category}"
        for i, group in enumerate(hooks[category]):
            validate_hook_group(group, f"{os_name}/{category}[{i}]")

    # JSON round-trip
    serialized = json.dumps(config, indent=2)
    roundtrip = json.loads(serialized)
    assert roundtrip == config, f"{os_name}: JSON round-trip mismatch"


def test(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except AssertionError as e:
        print(f"  [FAIL] {name}")
        print(f"         {e}")
        return False


def main():
    results = []

    linux = build_linux_config()
    windows = build_windows_config()

    print("--- structure ---")
    results.append(test("Linux config structure", lambda: validate_config(linux, "Linux")))
    results.append(test("Windows config structure", lambda: validate_config(windows, "Windows")))

    print("\n--- linux specifics ---")
    results.append(test("Linux has effortLevel", lambda: (
        assert_eq(linux.get("effortLevel"), "max")
    )))
    results.append(test("Linux deny list", lambda: (
        assert_eq(linux["permissions"]["deny"], ["Agent"])
    )))
    results.append(test("Linux hooks use unquoted paths", lambda: (
        assert_true(
            all('"' not in h["command"] for g in linux["hooks"]["PreToolUse"] for h in g["hooks"]),
            "Linux hook commands should not have quoted paths",
        )
    )))

    print("\n--- windows specifics ---")
    results.append(test("Windows has effortLevel", lambda: (
        assert_eq(windows.get("effortLevel"), "high")
    )))
    results.append(test("Windows deny list", lambda: (
        assert_eq(windows["permissions"]["deny"], ["Task", "Agent"])
    )))
    results.append(test("Windows hooks use quoted paths", lambda: (
        assert_true(
            all('"' in h["command"] for g in windows["hooks"]["PreToolUse"] for h in g["hooks"]),
            "Windows hook commands should have quoted paths",
        )
    )))
    results.append(test("Windows Stop has PowerShell notify", lambda: (
        assert_true(
            any("pwsh" in h["command"] for g in windows["hooks"]["Stop"] for h in g["hooks"]),
            "Windows Stop should have pwsh notify-complete",
        )
    )))

    print("\n--- cross-check ---")
    results.append(test("Both configs have inject-extension-rules-toml.py", lambda: check_both_have_hook(
        linux, windows, "inject-extension-rules-toml.py",
    )))
    results.append(test("Both configs have block-git-add-force-staging.py", lambda: check_both_have_hook(
        linux, windows, "block-git-add-force-staging.py",
    )))
    results.append(test("Both configs have block-non-python-hook-scripts.py", lambda: check_both_have_hook(
        linux, windows, "block-non-python-hook-scripts.py",
    )))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


def assert_true(condition, msg=""):
    assert condition, msg


def assert_eq(actual, expected):
    assert actual == expected, f"expected {expected!r}, got {actual!r}"


def check_both_have_hook(linux, windows, script_name):
    for os_name, config in [("Linux", linux), ("Windows", windows)]:
        found = any(
            script_name in h["command"]
            for groups in config["hooks"].values()
            for g in groups
            for h in g["hooks"]
        )
        assert found, f"{os_name} config missing {script_name}"


if __name__ == "__main__":
    main()
