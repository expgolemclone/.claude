"""Tests for stop-nixos-rebuild-on-config-change.py hook."""

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("stop-nixos-rebuild-on-config-change")
main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_run_result(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def run_main(stdin_data: dict) -> str:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


# ---------------------------------------------------------------------------
# Early returns (no rebuild triggered)
# ---------------------------------------------------------------------------

class TestEarlyReturn:
    def test_plan_mode(self):
        result = run_main({"permission_mode": "plan"})
        assert result == ""

    def test_dirty_tree(self):
        with mock.patch.object(mod, "run", return_value=make_run_result(stdout=" M file.nix")):
            result = run_main({})
        assert result == ""

    def test_rev_parse_fails(self):
        calls = [
            make_run_result(stdout=""),           # git status --porcelain (clean)
            make_run_result(returncode=1),        # git rev-parse HEAD (fail)
        ]
        with mock.patch.object(mod, "run", side_effect=calls):
            result = run_main({})
        assert result == ""


# ---------------------------------------------------------------------------
# Hash matches — skip rebuild
# ---------------------------------------------------------------------------

class TestSkipRebuild:
    def test_hash_unchanged(self, tmp_path):
        hash_file = tmp_path / "hash"
        hash_file.write_text("abc123")

        calls = [
            make_run_result(stdout=""),           # git status (clean)
            make_run_result(stdout="abc123\n"),    # git rev-parse HEAD
        ]
        with mock.patch.object(mod, "run", side_effect=calls), \
             mock.patch.object(mod, "HASH_FILE", hash_file):
            result = run_main({})
        assert result == ""


# ---------------------------------------------------------------------------
# Rebuild triggered
# ---------------------------------------------------------------------------

class TestRebuild:
    def test_success_updates_hash(self, tmp_path):
        hash_file = tmp_path / "hash"
        hash_file.write_text("old_hash")

        calls = [
            make_run_result(stdout=""),               # git status (clean)
            make_run_result(stdout="new_hash\n"),      # git rev-parse HEAD
            make_run_result(returncode=0),             # nixos-rebuild switch (success)
        ]
        with mock.patch.object(mod, "run", side_effect=calls), \
             mock.patch.object(mod, "HASH_FILE", hash_file):
            result = run_main({})

        assert result == ""
        assert hash_file.read_text() == "new_hash"

    def test_failure_blocks(self, tmp_path):
        hash_file = tmp_path / "hash"
        hash_file.write_text("old_hash")

        calls = [
            make_run_result(stdout=""),               # git status (clean)
            make_run_result(stdout="new_hash\n"),      # git rev-parse HEAD
            make_run_result(returncode=1, stderr="error: build failed"),  # rebuild fail
        ]
        with mock.patch.object(mod, "run", side_effect=calls), \
             mock.patch.object(mod, "HASH_FILE", hash_file):
            result = run_main({})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "build failed" in parsed["reason"]
        assert hash_file.read_text() == "old_hash"

    def test_first_run_no_hash_file(self, tmp_path):
        hash_file = tmp_path / "hash"

        calls = [
            make_run_result(stdout=""),               # git status (clean)
            make_run_result(stdout="first_hash\n"),    # git rev-parse HEAD
            make_run_result(returncode=0),             # nixos-rebuild switch (success)
        ]
        with mock.patch.object(mod, "run", side_effect=calls), \
             mock.patch.object(mod, "HASH_FILE", hash_file):
            result = run_main({})

        assert result == ""
        assert hash_file.read_text() == "first_hash"
