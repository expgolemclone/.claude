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
_suggest_command = mod._suggest_command
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
    def test_uv_run(self):
        assert is_code_execution("uv run app.py") is True

    def test_go_run(self):
        assert is_code_execution("go run main.go") is True

    def test_cargo_run(self):
        assert is_code_execution("cargo run") is True

    def test_dot_slash_binary(self):
        assert is_code_execution("./build/app") is True

    def test_uv_run_pytest_excluded(self):
        assert is_code_execution("uv run pytest") is False

    def test_cargo_test_excluded(self):
        assert is_code_execution("cargo test") is False

    def test_cargo_clippy_excluded(self):
        assert is_code_execution("cargo clippy") is False

    def test_uv_run_python_c_excluded(self):
        assert is_code_execution('uv run python3 -c "print(1)"') is False

    def test_no_match(self):
        assert is_code_execution("ls -la") is False

    def test_go_test_excluded(self):
        assert is_code_execution("go test ./...") is False

    def test_cargo_bench_excluded(self):
        assert is_code_execution("cargo bench") is False

    def test_uv_run_echo_excluded(self):
        assert is_code_execution("uv run echo hello") is False


# ---------------------------------------------------------------------------
# _looks_like_git_commit
# ---------------------------------------------------------------------------

class TestLooksLikeGitCommit:
    def test_git_commit(self):
        assert _looks_like_git_commit('git commit -m "msg"') is True

    def test_git_variable(self):
        assert _looks_like_git_commit("git $cmd") is True

    def test_git_push(self):
        assert _looks_like_git_commit("git push") is False

    def test_echo(self):
        assert _looks_like_git_commit("echo hello") is False

    def test_line_continuation(self):
        assert _looks_like_git_commit("git \\\ncommit -m 'x'") is True


# ---------------------------------------------------------------------------
# _cmd_references_file
# ---------------------------------------------------------------------------

class TestCmdReferencesFile:
    def test_full_path(self):
        assert _cmd_references_file("uv run /home/user/app.py", "/home/user/app.py") is True

    def test_basename(self):
        assert _cmd_references_file("uv run app.py", "/home/user/app.py") is True

    def test_no_match(self):
        assert _cmd_references_file("uv run other.py", "/home/user/app.py") is False


# ---------------------------------------------------------------------------
# _suggest_command
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_test_prefix(self):
        assert _is_test_file("/src/tests/test_app.py") is True

    def test_test_suffix(self):
        assert _is_test_file("/src/app_test.py") is True

    def test_regular_file(self):
        assert _is_test_file("/src/app.py") is False

    def test_conftest(self):
        assert _is_test_file("/src/tests/conftest.py") is False


# ---------------------------------------------------------------------------
# _is_test_execution
# ---------------------------------------------------------------------------

class TestIsTestExecution:
    def test_uv_run_pytest(self):
        assert _is_test_execution("uv run pytest tests/") is True

    def test_uv_run_python_m_pytest(self):
        assert _is_test_execution("uv run python3 -m pytest tests/") is True

    def test_go_test(self):
        assert _is_test_execution("go test ./...") is True

    def test_cargo_test(self):
        assert _is_test_execution("cargo test") is True

    def test_uv_run_app(self):
        assert _is_test_execution("uv run python3 app.py") is False

    def test_ls(self):
        assert _is_test_execution("ls -la") is False


# ---------------------------------------------------------------------------
# _suggest_command
# ---------------------------------------------------------------------------

class TestSuggestCommand:
    def test_python(self):
        assert _suggest_command("/src/app.py") == "uv run python3 /src/app.py"

    def test_python_test_file(self):
        assert _suggest_command("/src/tests/test_app.py") == "uv run pytest /src/tests/test_app.py"

    def test_go(self):
        assert _suggest_command("/src/main.go") == "go run /src/main.go"

    def test_rust(self):
        assert _suggest_command("/src/main.rs") == "cargo run"

    def test_c(self):
        assert _suggest_command("/src/app.c") == "gcc /src/app.c -o a.out && ./a.out"

    def test_cpp(self):
        assert _suggest_command("/src/app.cpp") == "g++ /src/app.cpp -o a.out && ./a.out"

    def test_cc(self):
        assert _suggest_command("/src/app.cc") == "g++ /src/app.cc -o a.out && ./a.out"


# ---------------------------------------------------------------------------
# main — block message contains suggested commands
# ---------------------------------------------------------------------------

class TestBlockMessageSuggestion:
    def test_python_suggestion_in_message(self, tmp_path):
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert "uv run python3 /src/app.py" in parsed["reason"]

    def test_test_file_suggestion_in_message(self, tmp_path):
        entries = [make_entry([make_edit_block("/src/tests/test_app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'test: add tests'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert "uv run pytest /src/tests/test_app.py" in parsed["reason"]

    def test_go_suggestion_in_message(self, tmp_path):
        entries = [make_entry([make_edit_block("/src/main.go")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add main'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert "go run /src/main.go" in parsed["reason"]


# ---------------------------------------------------------------------------
# main — block cases
# ---------------------------------------------------------------------------

class TestBlock:
    def test_edit_without_execution(self, tmp_path):
        entries = [
            make_entry([make_edit_block("/src/app.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_empty_transcript_path(self):
        payload = {
            "tool_input": {"command": "git commit -m 'x'"},
            "transcript_path": "",
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_unreadable_transcript(self):
        payload = {
            "tool_input": {"command": "git commit -m 'x'"},
            "transcript_path": "/nonexistent/path/transcript.jsonl",
        }
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"


# ---------------------------------------------------------------------------
# main — allow cases
# ---------------------------------------------------------------------------

class TestAllow:
    def test_non_commit_command(self, tmp_path):
        tp = write_transcript(tmp_path, [])
        payload = {
            "tool_input": {"command": "git push origin main"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_edit_then_execute(self, tmp_path):
        entries = [
            make_entry([make_edit_block("/src/app.py")]),
            make_entry([make_bash_block("uv run /src/app.py")]),
        ]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        result = run_main(payload)
        assert result == ""

    def test_non_code_extension(self, tmp_path):
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

    def test_test_file_edit_then_pytest(self, tmp_path):
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

    def test_pytest_does_not_verify_non_test_file(self, tmp_path):
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

    def test_no_edits_in_transcript(self, tmp_path):
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
