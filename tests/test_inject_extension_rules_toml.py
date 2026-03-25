"""Tests for inject-extension-rules-toml.py hook."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR
from tests.conftest import run_hook_process

HOOK = str(HOOKS_DIR / "inject-extension-rules-toml.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


def is_injected(result: dict | None) -> bool:
    return result is not None and "additionalContext" in result.get("hookSpecificOutput", {})


# ---------------------------------------------------------------------------
# Edit/Write: file extension rules
# ---------------------------------------------------------------------------

class TestFileExtension:
    def test_py_injects(self):
        assert is_injected(run_hook({"file_path": "/home/exp/project/main.py"}))

    def test_md_injects(self):
        assert is_injected(run_hook({"file_path": "/home/exp/docs/README.md"}))

    def test_rs_injects(self):
        assert is_injected(run_hook({"file_path": "/home/exp/project/main.rs"}))

    def test_cs_injects_common_only(self):
        result = run_hook({"file_path": "/home/exp/project/Program.cs"})
        assert is_injected(result)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "centralized_config" in ctx
        assert "[toolchain]" not in ctx


# ---------------------------------------------------------------------------
# Edit/Write: no injection
# ---------------------------------------------------------------------------

class TestNoInjection:
    def test_no_extension(self):
        assert not is_injected(run_hook({"file_path": "/home/exp/project/Makefile"}))

    def test_unknown_extension_injects_common_only(self):
        result = run_hook({"file_path": "/home/exp/project/data.xyz"})
        assert is_injected(result)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "centralized_config" in ctx

    def test_empty_file_path(self):
        assert not is_injected(run_hook({"file_path": ""}))

    def test_no_file_path_key(self):
        assert not is_injected(run_hook({"command": "echo hello"}))


# ---------------------------------------------------------------------------
# Bash: git command rules
# ---------------------------------------------------------------------------

class TestGitCommand:
    def test_git_commit_injects(self):
        assert is_injected(run_hook({"command": "git commit -m 'test'"}))

    def test_git_push_injects(self):
        assert is_injected(run_hook({"command": "git push origin main"}))

    def test_non_git_no_injection(self):
        assert not is_injected(run_hook({"command": "echo hello"}))
