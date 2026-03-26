"""Tests for block-platform-specific-scripts.py hook."""

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-platform-specific-scripts.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


class TestBlockUnixOnly:
    """Unix-only extensions should be blocked with Windows warning."""

    @pytest.mark.parametrize("ext", [".sh", ".bash", ".zsh", ".csh", ".tcsh", ".fish", ".ksh"])
    def test_unix_extensions(self, ext):
        result = run_hook({"file_path": f"/tmp/project/script{ext}"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_sh_uppercase(self):
        result = run_hook({"file_path": "/tmp/run.SH"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]


class TestBlockWindowsOnly:
    """Windows-only extensions should be blocked with Linux warning."""

    @pytest.mark.parametrize("ext", [".ps1", ".psm1", ".psd1", ".bat", ".cmd", ".vbs", ".vbe", ".wsf", ".wsh"])
    def test_windows_extensions(self, ext):
        result = run_hook({"file_path": f"C:/scripts/script{ext}"})
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
