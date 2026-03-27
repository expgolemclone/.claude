"""Tests for post-cargo-clippy-on-rs-edit.py hook."""

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
mod = importlib.import_module("post-cargo-clippy-on-rs-edit")
main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_main(stdin_data: dict) -> str:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


# ---------------------------------------------------------------------------
# main — skip cases
# ---------------------------------------------------------------------------

class TestSkip:
    def test_non_rs_file(self):
        result = run_main({"tool_input": {"file_path": "/src/main.py"}})
        assert result == ""

    def test_empty_file_path(self):
        result = run_main({"tool_input": {"file_path": ""}})
        assert result == ""

    def test_no_cargo_toml(self, tmp_path):
        rs_file = tmp_path / "isolated" / "lib.rs"
        rs_file.parent.mkdir()
        rs_file.touch()
        result = run_main({"tool_input": {"file_path": str(rs_file)}})
        assert result == ""


# ---------------------------------------------------------------------------
# main — clippy output
# ---------------------------------------------------------------------------

class TestClippyOutput:
    def test_warnings_injected(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.touch()

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="warning: unused variable"
        )
        with mock.patch("subprocess.run", return_value=fake_result):
            result = run_main({"tool_input": {"file_path": str(rs_file)}})

        parsed = json.loads(result)
        assert "hookSpecificOutput" in parsed
        assert "unused variable" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_clean_no_output(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.touch()

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch("subprocess.run", return_value=fake_result):
            result = run_main({"tool_input": {"file_path": str(rs_file)}})

        assert result == ""

    def test_timeout_no_output(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.touch()

        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cargo", 120)):
            result = run_main({"tool_input": {"file_path": str(rs_file)}})

        assert result == ""

    def test_cargo_not_found_no_output(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.touch()

        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            result = run_main({"tool_input": {"file_path": str(rs_file)}})

        assert result == ""
