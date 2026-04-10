"""Tests for block-commit-without-verification.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("block-commit-without-verification")
is_code_execution = mod.is_code_execution
_looks_like_git_commit = mod._looks_like_git_commit
_cmd_references_file = mod._cmd_references_file
_is_test_file = mod._is_test_file
_is_test_execution = mod._is_test_execution
main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_edit_block(file_path: str) -> dict:
    return {"type": "tool_use", "name": "Edit", "input": {"file_path": file_path}}


def make_bash_block(command: str) -> dict:
    return {"type": "tool_use", "name": "Bash", "input": {"command": command}}


def make_entry(blocks: list[dict], role: str = "assistant") -> dict:
    return {"type": role, "message": {"content": blocks}}


def write_transcript(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return p


def run_main(stdin_data: dict) -> str:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


# ---------------------------------------------------------------------------
# is_code_execution
# ---------------------------------------------------------------------------

class TestIsCodeExecution:
    # --- マッチするケース ---
    def test_uv_run_python3(self) -> None:
        assert is_code_execution("uv run python3 app.py") is True

    def test_uv_run_python(self) -> None:
        assert is_code_execution("uv run python app.py") is True

    def test_go_run(self) -> None:
        assert is_code_execution("go run main.go") is True

    def test_cargo_run(self) -> None:
        assert is_code_execution("cargo run") is True

    def test_dot_slash_binary(self) -> None:
        assert is_code_execution("./build/app") is True

    # --- 除外パターン ---
    def test_uv_run_python_c_excluded(self) -> None:
        assert is_code_execution('uv run python3 -c "print(1)"') is False

    def test_uv_run_python_m_pytest_excluded(self) -> None:
        assert is_code_execution("uv run python3 -m pytest tests/") is False

    # --- _EXEC_PATTERNS にマッチしない ---
    def test_uv_run_ruff_not_matched(self) -> None:
        assert is_code_execution("uv run ruff check file.py") is False

    def test_uv_run_mypy_not_matched(self) -> None:
        assert is_code_execution("uv run mypy file.py") is False

    def test_uv_run_black_not_matched(self) -> None:
        assert is_code_execution("uv run black file.py") is False

    def test_uv_run_pytest_not_matched(self) -> None:
        assert is_code_execution("uv run pytest") is False

    def test_uv_run_echo_not_matched(self) -> None:
        assert is_code_execution("uv run echo hello") is False

    def test_cargo_test_not_matched(self) -> None:
        assert is_code_execution("cargo test") is False

    def test_cargo_clippy_not_matched(self) -> None:
        assert is_code_execution("cargo clippy") is False

    def test_go_test_not_matched(self) -> None:
        assert is_code_execution("go test ./...") is False

    def test_no_match(self) -> None:
        assert is_code_execution("ls -la") is False


# ---------------------------------------------------------------------------
# _looks_like_git_commit
# ---------------------------------------------------------------------------

class TestLooksLikeGitCommit:
    def test_git_commit(self) -> None:
        assert _looks_like_git_commit('git commit -m "msg"') is True

    def test_git_variable(self) -> None:
        assert _looks_like_git_commit("git $cmd") is True

    def test_git_push(self) -> None:
        assert _looks_like_git_commit("git push") is False

    def test_echo(self) -> None:
        assert _looks_like_git_commit("echo hello") is False

    def test_line_continuation(self) -> None:
        assert _looks_like_git_commit("git \\\ncommit -m 'x'") is True


# ---------------------------------------------------------------------------
# _cmd_references_file
# ---------------------------------------------------------------------------

class TestCmdReferencesFile:
    def test_full_path(self) -> None:
        assert _cmd_references_file("uv run /home/user/app.py", "/home/user/app.py") is True

    def test_basename(self) -> None:
        assert _cmd_references_file("uv run app.py", "/home/user/app.py") is True

    def test_no_match(self) -> None:
        assert _cmd_references_file("uv run other.py", "/home/user/app.py") is False


# ---------------------------------------------------------------------------
# _is_test_file / _is_test_execution
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_test_prefix(self) -> None:
        assert _is_test_file("/src/tests/test_app.py") is True

    def test_test_suffix(self) -> None:
        assert _is_test_file("/src/app_test.py") is True

    def test_regular_file(self) -> None:
        assert _is_test_file("/src/app.py") is False

    def test_conftest(self) -> None:
        assert _is_test_file("/src/tests/conftest.py") is False


class TestIsTestExecution:
    def test_uv_run_pytest(self) -> None:
        assert _is_test_execution("uv run pytest tests/") is True

    def test_uv_run_python_m_pytest(self) -> None:
        assert _is_test_execution("uv run python3 -m pytest tests/") is True

    def test_go_test(self) -> None:
        assert _is_test_execution("go test ./...") is True

    def test_cargo_test(self) -> None:
        assert _is_test_execution("cargo test") is True

    def test_uv_run_app(self) -> None:
        assert _is_test_execution("uv run python3 app.py") is False

    def test_ls(self) -> None:
        assert _is_test_execution("ls -la") is False


# ---------------------------------------------------------------------------
# main — allow cases
# ---------------------------------------------------------------------------

class TestAllow:
    def test_non_commit_command(self, tmp_path: Path) -> None:
        tp = write_transcript(tmp_path, [])
        payload = {
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_edit_then_execute(self, tmp_path: Path) -> None:
        entries = [
            make_entry([make_edit_block("/src/app.py")]),
            make_entry([make_bash_block("uv run python3 /src/app.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_non_code_extension(self, tmp_path: Path) -> None:
        entries = [
            make_entry([make_edit_block("/docs/readme.md")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'docs: update'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_test_file_edit_then_pytest(self, tmp_path: Path) -> None:
        entries = [
            make_entry([make_edit_block("/src/tests/test_app.py")]),
            make_entry([make_bash_block("uv run pytest /src/tests/test_app.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'test: add tests'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_hooks_dir_excluded(self, tmp_path: Path) -> None:
        """hooks/ディレクトリのファイルは検証対象外."""
        entries = [
            make_entry([make_edit_block("/home/user/.claude/hooks/my-hook.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: hook'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_no_edits_in_transcript(self, tmp_path: Path) -> None:
        entries = [
            make_entry([make_bash_block("ls -la")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'chore: cleanup'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""


# ---------------------------------------------------------------------------
# main — block cases
# ---------------------------------------------------------------------------

class TestBlock:
    def test_empty_transcript_path(self) -> None:
        payload = {
            "tool_input": {"command": "git commit -m 'x'"},
            "transcript_path": "",
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_unreadable_transcript(self) -> None:
        payload = {
            "tool_input": {"command": "git commit -m 'x'"},
            "transcript_path": "/nonexistent/path/transcript.jsonl",
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_unverified_edit_blocks(self, tmp_path: Path) -> None:
        """編集済みだが実行されていないファイルがあればblock."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_pytest_does_not_verify_non_test_file(self, tmp_path: Path) -> None:
        """pytestはテストファイル以外の検証にならない."""
        entries = [
            make_entry([make_edit_block("/src/app.py")]),
            make_entry([make_bash_block("uv run pytest /src/app.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
