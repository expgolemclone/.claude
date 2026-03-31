"""Tests for stop-lint-edited-python.py hook."""

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
mod = importlib.import_module("stop-lint-edited-python")
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
# Skip conditions
# ---------------------------------------------------------------------------

class TestSkip:
    def test_stop_hook_active(self) -> None:
        result = run_main({"stop_hook_active": True})
        assert result == ""

    def test_plan_mode(self) -> None:
        result = run_main({"permission_mode": "plan"})
        assert result == ""

    def test_no_changed_files(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "lint-hashes.json"
        py_file = tmp_path / "hooks" / "example.py"
        py_file.parent.mkdir()
        py_file.write_text("x: int = 1\n")

        # Pre-populate cache with current hash
        current_hash = mod.file_sha256(py_file)
        cache_file.write_text(json.dumps({str(py_file): current_hash}))

        with (
            mock.patch.object(mod, "CACHE_FILE", cache_file),
            mock.patch.object(mod, "HOOKS_DIR", tmp_path / "hooks"),
        ):
            result = run_main({})

        assert result == ""


# ---------------------------------------------------------------------------
# Linter execution
# ---------------------------------------------------------------------------

class TestLinterExecution:
    def test_block_on_lint_errors(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".cache" / "lint-hashes.json"
        py_file = tmp_path / "hooks" / "bad.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("def f(x=[]):\n    pass\n")

        fake_fail = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="error: found issue", stderr=""
        )

        with (
            mock.patch.object(mod, "CACHE_FILE", cache_file),
            mock.patch.object(mod, "HOOKS_DIR", tmp_path / "hooks"),
            mock.patch("subprocess.run", return_value=fake_fail),
        ):
            result = run_main({})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "error: found issue" in parsed["reason"]

    def test_pass_updates_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".cache" / "lint-hashes.json"
        py_file = tmp_path / "hooks" / "good.py"
        py_file.parent.mkdir(parents=True)
        (tmp_path / ".cache").mkdir()

        py_file.write_text("def f(x: int) -> None:\n    pass\n")

        fake_ok = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with (
            mock.patch.object(mod, "CACHE_FILE", cache_file),
            mock.patch.object(mod, "HOOKS_DIR", tmp_path / "hooks"),
            mock.patch.object(mod, "PROJECT_ROOT", tmp_path),
            mock.patch("subprocess.run", return_value=fake_ok),
        ):
            result = run_main({})

        assert result == ""
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert str(py_file) in cached

    def test_timeout_reported(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".cache" / "lint-hashes.json"
        py_file = tmp_path / "hooks" / "slow.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("x: int = 1\n")

        with (
            mock.patch.object(mod, "CACHE_FILE", cache_file),
            mock.patch.object(mod, "HOOKS_DIR", tmp_path / "hooks"),
            mock.patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("cmd", 120),
            ),
        ):
            result = run_main({})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "timed out" in parsed["reason"]


# ---------------------------------------------------------------------------
# build_commands
# ---------------------------------------------------------------------------

class TestBuildCommands:
    def test_module_mode(self) -> None:
        cli_cfg = {
            "python_linters": {
                "python_warning_flag": "error",
                "runner": ["uv", "run"],
                "tools": {
                    "mypy": {"module": "mypy"},
                    "ruff": {"module": "ruff", "args": ["check"]},
                    "pylint": {"module": "pylint"},
                },
            }
        }
        files = [Path("/tmp/test.py")]
        commands = mod.build_commands(files, cli_cfg)

        assert len(commands) == 3

        _, mypy_cmd = commands[0]
        assert mypy_cmd == [
            "uv", "run", "python3", "-W", "error", "-m", "mypy", "/tmp/test.py"
        ]

        _, ruff_cmd = commands[1]
        assert ruff_cmd == [
            "uv", "run", "python3", "-W", "error", "-m", "ruff", "check", "/tmp/test.py"
        ]

    def test_command_mode(self) -> None:
        cli_cfg = {
            "python_linters": {
                "python_warning_flag": "error",
                "runner": ["uv", "run"],
                "tools": {
                    "mypy": {"module": "mypy"},
                    "ruff": {"command": ["nix", "run", "nixpkgs#ruff", "--"], "args": ["check"]},
                    "pylint": {"module": "pylint"},
                },
            }
        }
        files = [Path("/tmp/test.py")]
        commands = mod.build_commands(files, cli_cfg)

        _, ruff_cmd = commands[1]
        assert ruff_cmd == [
            "nix", "run", "nixpkgs#ruff", "--", "check", "/tmp/test.py"
        ]

        # module tools still use runner + python3 -W error -m
        _, mypy_cmd = commands[0]
        assert mypy_cmd[:6] == ["uv", "run", "python3", "-W", "error", "-m"]


# ---------------------------------------------------------------------------
# Hash cache
# ---------------------------------------------------------------------------

class TestHashCache:
    def test_first_run_checks_all(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".cache" / "lint-hashes.json"
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "a.py").write_text("a: int = 1\n")
        (hooks_dir / "b.py").write_text("b: int = 2\n")

        cached = mod.load_cache.__wrapped__(cache_file) if hasattr(mod.load_cache, "__wrapped__") else {}
        with mock.patch.object(mod, "CACHE_FILE", cache_file):
            cached = mod.load_cache()

        with mock.patch.object(mod, "HOOKS_DIR", hooks_dir):
            files, current = mod.changed_files(cached)

        assert len(files) == 2
        assert len(current) == 2

    def test_unchanged_files_skipped(self, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        py_file = hooks_dir / "a.py"
        py_file.write_text("a: int = 1\n")

        digest = mod.file_sha256(py_file)
        cached = {str(py_file): digest}

        with mock.patch.object(mod, "HOOKS_DIR", hooks_dir):
            files, _ = mod.changed_files(cached)

        assert files == []
