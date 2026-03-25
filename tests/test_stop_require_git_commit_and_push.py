"""Tests for stop-require-git-commit-and-push.py hook."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "stop-require-git-commit-and-push.py")


def run_hook(data: dict) -> dict | None:
    return run_hook_process(HOOK, data)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


@pytest.fixture()
def dirty_repo(tmp_path: Path) -> Path:
    """Git repo with uncommitted changes."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("hello")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    (tmp_path / "b.txt").write_text("uncommitted")
    return tmp_path


@pytest.fixture()
def clean_repo(tmp_path: Path) -> Path:
    """Git repo with no uncommitted changes."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("hello")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


# ---------------------------------------------------------------------------
# Early return conditions
# ---------------------------------------------------------------------------

class TestEarlyReturn:
    def test_stop_hook_active(self, dirty_repo):
        assert run_hook({"stop_hook_active": True, "cwd": str(dirty_repo)}) is None

    def test_plan_mode(self, dirty_repo):
        assert run_hook({"permission_mode": "plan", "cwd": str(dirty_repo)}) is None


# ---------------------------------------------------------------------------
# Git repo with changes
# ---------------------------------------------------------------------------

class TestGitRepo:
    def test_uncommitted_changes_blocks(self, dirty_repo):
        result = run_hook({"cwd": str(dirty_repo)})
        assert result is not None
        assert result["decision"] == "block"

    def test_clean_repo_allows(self, clean_repo):
        result = run_hook({"cwd": str(clean_repo)})
        assert result is None


# ---------------------------------------------------------------------------
# Not a git repo
# ---------------------------------------------------------------------------

class TestNonGitDir:
    def test_tempdir_not_git_repo(self):
        assert run_hook({"cwd": tempfile.gettempdir()}) is None
