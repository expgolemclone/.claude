"""Tests for stop-require-git-commit-and-push.py hook."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR
from tests.conftest import run_hook_process

HOOK = str(HOOKS_DIR / "stop-require-git-commit-and-push.py")


def run_hook(data: dict) -> dict | None:
    return run_hook_process(HOOK, data)


# ---------------------------------------------------------------------------
# Early return conditions
# ---------------------------------------------------------------------------

class TestEarlyReturn:
    def test_stop_hook_active(self):
        assert run_hook({"stop_hook_active": True, "cwd": str(HOOKS_DIR)}) is None

    def test_plan_mode(self):
        assert run_hook({"permission_mode": "plan", "cwd": str(HOOKS_DIR)}) is None


# ---------------------------------------------------------------------------
# Git repo with changes
# ---------------------------------------------------------------------------

class TestGitRepo:
    def test_uncommitted_changes_blocks(self):
        result = run_hook({"cwd": str(HOOKS_DIR)})
        assert result is not None
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Not a git repo
# ---------------------------------------------------------------------------

class TestNonGitDir:
    def test_tempdir_not_git_repo(self):
        assert run_hook({"cwd": tempfile.gettempdir()}) is None
