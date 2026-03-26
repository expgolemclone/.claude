"""Tests for block-platform-specific-scripts.py hook."""

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-platform-specific-scripts.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


class TestBlockUnixOnly:
    """Unix-only extensions (.sh, .bash) should be blocked with Windows warning."""

    def test_sh(self):
        result = run_hook({"file_path": "/tmp/project/deploy.sh"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_bash(self):
        result = run_hook({"file_path": "/home/user/setup.bash"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_sh_uppercase(self):
        result = run_hook({"file_path": "/tmp/run.SH"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]


class TestBlockWindowsOnly:
    """Windows-only extensions (.ps1, .bat, .cmd) should be blocked with Linux warning."""

    def test_ps1(self):
        result = run_hook({"file_path": "C:/Users/me/script.ps1"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]

    def test_bat(self):
        result = run_hook({"file_path": "C:/scripts/run.bat"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]

    def test_cmd(self):
        result = run_hook({"file_path": "C:/scripts/build.cmd"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]


class TestAllow:
    """Non-platform-specific extensions should pass through."""

    def test_py(self):
        assert run_hook({"file_path": "/tmp/script.py"}) is None

    def test_txt(self):
        assert run_hook({"file_path": "/tmp/notes.txt"}) is None

    def test_no_file_path(self):
        assert run_hook({}) is None

    def test_empty_file_path(self):
        assert run_hook({"file_path": ""}) is None
