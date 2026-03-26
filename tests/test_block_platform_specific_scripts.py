"""Tests for block-platform-specific-scripts.py hook."""

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-platform-specific-scripts.py")

UNIX_EXTS = [".sh", ".bash", ".zsh", ".csh", ".tcsh", ".fish", ".ksh"]
WINDOWS_EXTS = [".ps1", ".psm1", ".psd1", ".bat", ".cmd", ".vbs", ".vbe", ".wsf", ".wsh"]


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Write tool
# ---------------------------------------------------------------------------

class TestWriteBlockUnixOnly:
    """Write: Unix-only extensions should be blocked with Windows warning."""

    @pytest.mark.parametrize("ext", UNIX_EXTS)
    def test_unix_extensions(self, ext):
        result = run_hook({"file_path": f"/tmp/project/script{ext}"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_sh_uppercase(self):
        result = run_hook({"file_path": "/tmp/run.SH"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]


class TestWriteBlockWindowsOnly:
    """Write: Windows-only extensions should be blocked with Linux warning."""

    @pytest.mark.parametrize("ext", WINDOWS_EXTS)
    def test_windows_extensions(self, ext):
        result = run_hook({"file_path": f"C:/scripts/script{ext}"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]


class TestWriteAllow:
    """Write: Non-platform-specific extensions should pass through."""

    def test_py(self):
        assert run_hook({"file_path": "/tmp/script.py"}) is None

    def test_txt(self):
        assert run_hook({"file_path": "/tmp/notes.txt"}) is None

    def test_no_file_path(self):
        assert run_hook({}) is None

    def test_empty_file_path(self):
        assert run_hook({"file_path": ""}) is None


# ---------------------------------------------------------------------------
# Bash tool
# ---------------------------------------------------------------------------

class TestBashBlockRedirect:
    """Bash: redirect (> / >>) to platform-specific files should be blocked."""

    def test_redirect_sh(self):
        result = run_hook({"command": "echo '#!/bin/bash' > deploy.sh"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_append_redirect_bat(self):
        result = run_hook({"command": "echo @echo off >> run.bat"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]

    def test_cat_heredoc_ps1(self):
        result = run_hook({"command": "cat <<'EOF' > setup.ps1"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]


class TestBashBlockTouch:
    """Bash: touch creating platform-specific files should be blocked."""

    def test_touch_sh(self):
        result = run_hook({"command": "touch script.sh"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_touch_bat(self):
        result = run_hook({"command": "touch run.bat"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]


class TestBashBlockTee:
    """Bash: tee to platform-specific files should be blocked."""

    def test_tee_sh(self):
        result = run_hook({"command": "echo hello | tee output.sh"})
        assert result["decision"] == "block"
        assert "Windows" in result["reason"]

    def test_tee_append_vbs(self):
        result = run_hook({"command": "echo hello | tee -a output.vbs"})
        assert result["decision"] == "block"
        assert "Linux" in result["reason"]


class TestBashAllow:
    """Bash: commands not creating platform-specific files should pass."""

    def test_redirect_py(self):
        assert run_hook({"command": "echo test > script.py"}) is None

    def test_cat_sh(self):
        assert run_hook({"command": "cat deploy.sh"}) is None

    def test_rm_bat(self):
        assert run_hook({"command": "rm run.bat"}) is None

    def test_empty_command(self):
        assert run_hook({"command": ""}) is None
