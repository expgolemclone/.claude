"""Tests for setup.py: verify both OS configs generate valid settings.json."""

import json
from pathlib import Path

import pytest

from setup import build_linux_config, build_windows_config
from tests.conftest import HOOKS_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_hook_entry(entry, context):
    assert "type" in entry, f"{context}: missing 'type'"
    assert entry["type"] == "command", f"{context}: type must be 'command', got {entry['type']}"
    assert "command" in entry, f"{context}: missing 'command'"
    assert len(entry["command"]) > 0, f"{context}: empty command"


def validate_hook_group(group, context):
    assert "hooks" in group, f"{context}: missing 'hooks'"
    assert len(group["hooks"]) > 0, f"{context}: empty hooks list"
    for i, entry in enumerate(group["hooks"]):
        validate_hook_entry(entry, f"{context}[{i}]")


def validate_config(config, os_name):
    assert "permissions" in config, f"{os_name}: missing permissions"
    assert "skipDangerousModePermissionPrompt" in config
    assert config["skipDangerousModePermissionPrompt"] is True
    assert "hooks" in config

    perms = config["permissions"]
    assert perms["defaultMode"] == "bypassPermissions"

    hooks = config["hooks"]
    for category in ("PreToolUse", "PostToolUse", "Stop"):
        assert category in hooks, f"{os_name}: missing {category}"
        assert len(hooks[category]) > 0, f"{os_name}: empty {category}"
        for i, group in enumerate(hooks[category]):
            validate_hook_group(group, f"{os_name}/{category}[{i}]")

    serialized = json.dumps(config, indent=2)
    roundtrip = json.loads(serialized)
    assert roundtrip == config, f"{os_name}: JSON round-trip mismatch"


def check_both_have_hook(linux, windows, script_name):
    for os_name, config in [("Linux", linux), ("Windows", windows)]:
        found = any(
            script_name in h["command"]
            for groups in config["hooks"].values()
            for g in groups
            for h in g["hooks"]
        )
        assert found, f"{os_name} config missing {script_name}"


def all_hook_scripts(config):
    """Extract all script filenames referenced in a config."""
    scripts = []
    for groups in config["hooks"].values():
        for g in groups:
            for h in g["hooks"]:
                cmd = h["command"]
                for part in cmd.split():
                    if part.strip('"').endswith(".py"):
                        scripts.append(Path(part.strip('"')).name)
    return scripts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def linux():
    return build_linux_config()


@pytest.fixture(scope="module")
def windows():
    return build_windows_config()


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_linux_config_structure(self, linux):
        validate_config(linux, "Linux")

    def test_windows_config_structure(self, windows):
        validate_config(windows, "Windows")


# ---------------------------------------------------------------------------
# Linux specifics
# ---------------------------------------------------------------------------

class TestLinux:
    def test_no_model(self, linux):
        assert "model" not in linux

    def test_deny_list(self, linux):
        assert linux["permissions"]["deny"] == ["Agent"]

    def test_hooks_use_unquoted_paths(self, linux):
        for g in linux["hooks"]["PreToolUse"]:
            for h in g["hooks"]:
                assert '"' not in h["command"], "Linux hook commands should not have quoted paths"


# ---------------------------------------------------------------------------
# Windows specifics
# ---------------------------------------------------------------------------

class TestWindows:
    def test_has_effort_level(self, windows):
        assert windows.get("effortLevel") == "max"

    def test_deny_list(self, windows):
        assert windows["permissions"]["deny"] == ["Task", "Agent"]

    def test_hooks_use_quoted_paths(self, windows):
        for g in windows["hooks"]["PreToolUse"]:
            for h in g["hooks"]:
                assert '"' in h["command"], "Windows hook commands should have quoted paths"

    def test_stop_has_powershell_notify(self, windows):
        has_pwsh = any(
            "pwsh" in h["command"]
            for g in windows["hooks"]["Stop"]
            for h in g["hooks"]
        )
        assert has_pwsh, "Windows Stop should have pwsh notify-complete"


# ---------------------------------------------------------------------------
# Cross-check
# ---------------------------------------------------------------------------

class TestCrossCheck:
    def test_both_have_inject_extension_rules(self, linux, windows):
        check_both_have_hook(linux, windows, "inject-extension-rules-toml.py")

    def test_both_have_block_git_add_force(self, linux, windows):
        check_both_have_hook(linux, windows, "block-git-add-force-staging.py")

    def test_both_have_block_non_python_hooks(self, linux, windows):
        check_both_have_hook(linux, windows, "block-non-python-hook-scripts.py")

    def test_shared_hooks_present_in_both(self, linux, windows):
        """OS-agnostic hooks must be registered in both configs."""
        OS_SPECIFIC = {
            "block-protected-nix-config.py",
            "block-git-commit-protected-changes.py",
            "block-nixos-rebuild-protected-changes.py",
            "post-verify-protected-nix-config.py",
            "stop-nixos-rebuild-on-config-change.py",
            "check-hotstring-conflicts.py",
            "notify-complete.ps1",
        }
        linux_scripts = set(all_hook_scripts(linux)) - OS_SPECIFIC
        windows_scripts = set(all_hook_scripts(windows)) - OS_SPECIFIC
        only_linux = linux_scripts - windows_scripts
        only_windows = windows_scripts - linux_scripts
        assert not only_linux, f"Registered in Linux only: {only_linux}"
        assert not only_windows, f"Registered in Windows only: {only_windows}"


# ---------------------------------------------------------------------------
# Hook file existence
# ---------------------------------------------------------------------------

class TestHookFileExistence:
    def test_linux_hook_scripts_exist(self, linux):
        for script in all_hook_scripts(linux):
            assert (HOOKS_DIR / script).exists(), f"Linux references missing hook: {script}"

    def test_windows_hook_scripts_exist(self, windows):
        for script in all_hook_scripts(windows):
            if script.endswith(".ps1"):
                continue  # PowerShell scripts in scripts/ dir
            assert (HOOKS_DIR / script).exists(), f"Windows references missing hook: {script}"
