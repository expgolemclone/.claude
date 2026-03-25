"""Tests for block-git-commit-protected-changes.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("block-git-commit-protected-changes")
main = mod.main

# Reuse diff fixtures from rebuild hook tests
from test_block_nixos_rebuild_protected_changes import (
    DIFF_MKFORCE_OVERRIDE,
    DIFF_PASSWORD_REMOVED,
    DIFF_SAFE_CHANGE,
    DIFF_SYSUSERS_CHANGED,
)


def run_main(command: str, staged_diff: str = "") -> dict | None:
    stdin_data = {"tool_input": {"command": command}}
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            with mock.patch.object(mod, "get_staged_diff", return_value=staged_diff):
                main()
        raw = out.getvalue()
        return json.loads(raw) if raw else None


# ---------------------------------------------------------------------------
# Command detection
# ---------------------------------------------------------------------------

class TestCommandDetection:
    def test_1_non_commit_passes(self):
        result = run_main("git status", DIFF_SYSUSERS_CHANGED)
        assert result is None

    def test_2_git_commit_detected(self):
        result = run_main('git commit -m "fix"', DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"

    def test_3_git_add_then_commit(self):
        result = run_main('git add . && git commit -m "fix"', DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Staged diff — should block
# ---------------------------------------------------------------------------

class TestBlock:
    def test_4_sysusers_staged(self):
        result = run_main('git commit -m "x"', DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"

    def test_5_password_removed_staged(self):
        result = run_main('git commit -m "x"', DIFF_PASSWORD_REMOVED)
        assert result["decision"] == "block"

    def test_6_mkforce_staged(self):
        result = run_main('git commit -m "x"', DIFF_MKFORCE_OVERRIDE)
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Staged diff — should pass
# ---------------------------------------------------------------------------

class TestPass:
    def test_7_safe_change(self):
        result = run_main('git commit -m "x"', DIFF_SAFE_CHANGE)
        assert result is None

    def test_8_empty_staged(self):
        result = run_main('git commit -m "x"', "")
        assert result is None

    def test_9_git_push_not_affected(self):
        result = run_main("git push", DIFF_SYSUSERS_CHANGED)
        assert result is None
