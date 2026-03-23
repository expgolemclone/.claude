"""Tests for block-git-add-force-staging.py hook."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR
from tests.conftest import run_hook_process

HOOK = str(HOOKS_DIR / "block-git-add-force-staging.py")


def run_hook(command: str) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": {"command": command}})


# ---------------------------------------------------------------------------
# Should block
# ---------------------------------------------------------------------------

class TestBlock:
    def test_git_add_f(self):
        result = run_hook("git add -f .")
        assert result["decision"] == "block"

    def test_git_add_force(self):
        result = run_hook("git add --force somefile.txt")
        assert result["decision"] == "block"

    def test_git_add_f_with_path(self):
        result = run_hook("git add -f node_modules/")
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------

class TestAllow:
    def test_normal_git_add(self):
        assert run_hook("git add .") is None

    def test_git_add_specific_file(self):
        assert run_hook("git add main.py") is None

    def test_not_a_git_command(self):
        assert run_hook("echo hello") is None

    def test_f_inside_quotes(self):
        assert run_hook('git commit -m "add -f feature flag"') is None
