"""Tests for block-commit-without-verification.py hook."""

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
mod = importlib.import_module("block-commit-without-verification")
is_code_execution = mod.is_code_execution
_looks_like_git_commit = mod._looks_like_git_commit
_cmd_references_file = mod._cmd_references_file
_is_test_file = mod._is_test_file
_is_test_execution = mod._is_test_execution
_build_exec_plan = mod._build_exec_plan
_execute_file = mod._execute_file
_load_cache = mod._load_cache
_save_cache = mod._save_cache
_format_results = mod._format_results
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


def make_success_result(args=None, stdout="ok\n", stderr=""):
    return subprocess.CompletedProcess(args=args or [], returncode=0, stdout=stdout, stderr=stderr)


def make_failure_result(args=None, stdout="", stderr="error: something wrong\n", returncode=1):
    return subprocess.CompletedProcess(args=args or [], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# is_code_execution
# ---------------------------------------------------------------------------

class TestIsCodeExecution:
    # --- マッチするケース ---
    def test_uv_run_python3(self):
        assert is_code_execution("uv run python3 app.py") is True

    def test_uv_run_python(self):
        assert is_code_execution("uv run python app.py") is True

    def test_go_run(self):
        assert is_code_execution("go run main.go") is True

    def test_cargo_run(self):
        assert is_code_execution("cargo run") is True

    def test_dot_slash_binary(self):
        assert is_code_execution("./build/app") is True

    # --- 除外パターン ---
    def test_uv_run_python_c_excluded(self):
        assert is_code_execution('uv run python3 -c "print(1)"') is False

    def test_uv_run_python_m_pytest_excluded(self):
        assert is_code_execution("uv run python3 -m pytest tests/") is False

    # --- _EXEC_PATTERNS にマッチしない ---
    def test_uv_run_ruff_not_matched(self):
        assert is_code_execution("uv run ruff check file.py") is False

    def test_uv_run_mypy_not_matched(self):
        assert is_code_execution("uv run mypy file.py") is False

    def test_uv_run_black_not_matched(self):
        assert is_code_execution("uv run black file.py") is False

    def test_uv_run_pytest_not_matched(self):
        assert is_code_execution("uv run pytest") is False

    def test_uv_run_echo_not_matched(self):
        assert is_code_execution("uv run echo hello") is False

    def test_cargo_test_not_matched(self):
        assert is_code_execution("cargo test") is False

    def test_cargo_clippy_not_matched(self):
        assert is_code_execution("cargo clippy") is False

    def test_go_test_not_matched(self):
        assert is_code_execution("go test ./...") is False

    def test_no_match(self):
        assert is_code_execution("ls -la") is False


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
# _is_test_file / _is_test_execution
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
# _build_exec_plan
# ---------------------------------------------------------------------------

class TestBuildExecPlan:
    def test_python(self):
        plan = _build_exec_plan("/src/app.py")
        assert plan.steps == [["uv", "run", "python3", "/src/app.py"]]
        assert plan.tmp_file is None

    def test_python_test(self):
        plan = _build_exec_plan("/src/tests/test_app.py")
        assert plan.steps == [["uv", "run", "pytest", "/src/tests/test_app.py"]]

    def test_go(self):
        plan = _build_exec_plan("/src/main.go")
        assert plan.steps == [["go", "run", "/src/main.go"]]

    def test_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        rs_file = str(tmp_path / "src" / "main.rs")
        plan = _build_exec_plan(rs_file)
        assert plan.steps == [["cargo", "run"]]
        assert plan.cwd == str(tmp_path)

    def test_c(self):
        plan = _build_exec_plan("/src/app.c")
        assert len(plan.steps) == 2
        assert plan.steps[0][0] == "gcc"
        assert plan.tmp_file is not None

    def test_cpp(self):
        plan = _build_exec_plan("/src/app.cpp")
        assert plan.steps[0][0] == "g++"

    def test_unknown_ext(self):
        plan = _build_exec_plan("/src/readme.md")
        assert plan.steps == []


# ---------------------------------------------------------------------------
# _execute_file
# ---------------------------------------------------------------------------

class TestExecuteFile:
    def test_success(self):
        with mock.patch("subprocess.run", return_value=make_success_result()):
            fp, code, output = _execute_file("/src/app.py")
        assert fp == "/src/app.py"
        assert code == 0
        assert "ok" in output

    def test_failure(self):
        with mock.patch("subprocess.run", return_value=make_failure_result()):
            fp, code, output = _execute_file("/src/app.py")
        assert code == 1
        assert "error" in output

    def test_timeout(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            fp, code, output = _execute_file("/src/app.py")
        assert code == 1
        assert "timeout" in output

    def test_command_not_found(self):
        err = FileNotFoundError()
        err.filename = "uv"
        with mock.patch("subprocess.run", side_effect=err):
            fp, code, output = _execute_file("/src/app.py")
        assert code == 1
        assert "uv" in output

    def test_no_steps(self):
        fp, code, output = _execute_file("/src/readme.md")
        assert code == 0
        assert output == ""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_load_missing(self, tmp_path):
        tp = str(tmp_path / "transcript.jsonl")
        assert _load_cache(tp) == {}

    def test_save_and_load(self, tmp_path):
        tp = str(tmp_path / "transcript.jsonl")
        results = [("/src/app.py", 0, "ok")]
        edited = {"/src/app.py": 5}
        _save_cache(tp, {}, results, edited)
        cache = _load_cache(tp)
        assert cache["/src/app.py"]["edit_seq"] == 5
        assert cache["/src/app.py"]["exit_code"] == 0

    def test_load_corrupt(self, tmp_path):
        cache_file = tmp_path / "verification-cache.json"
        cache_file.write_text("not json")
        tp = str(tmp_path / "transcript.jsonl")
        assert _load_cache(tp) == {}


# ---------------------------------------------------------------------------
# _format_results
# ---------------------------------------------------------------------------

class TestFormatResults:
    def test_success_format(self):
        text = _format_results([("/src/app.py", 0, "hello")])
        assert "[OK]" in text
        assert "hello" in text

    def test_failure_format(self):
        text = _format_results([("/src/app.py", 1, "error msg")])
        assert "FAILED" in text
        assert "exit 1" in text

    def test_no_output(self):
        text = _format_results([("/src/app.py", 0, "")])
        assert "(no output)" in text


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
            make_entry([make_bash_block("uv run python3 /src/app.py")]),
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
        with mock.patch("subprocess.run", return_value=make_success_result()):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_hooks_dir_excluded(self, tmp_path):
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


# ---------------------------------------------------------------------------
# main — block cases
# ---------------------------------------------------------------------------

class TestBlock:
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
# main — auto-execution flow
# ---------------------------------------------------------------------------

class TestAutoExecution:
    def test_first_attempt_runs_and_blocks(self, tmp_path):
        """初回commitで自動実行し、結果付きでblockする."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        with mock.patch("subprocess.run", return_value=make_success_result()):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "コード検証結果" in parsed["reason"]
        assert "[OK]" in parsed["reason"]

    def test_second_attempt_cache_hit_approves(self, tmp_path):
        """2回目のcommitでキャッシュヒットしapproveする."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        # 1回目: 実行してblock
        with mock.patch("subprocess.run", return_value=make_success_result()):
            run_main(payload)
        # 2回目: キャッシュヒットでapprove
        result = run_main(payload)
        assert result == ""

    def test_cached_failure_still_blocks(self, tmp_path):
        """キャッシュ済みでもエラーがあれば2回目もblockする."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        # 1回目: 実行失敗→block
        with mock.patch("subprocess.run", return_value=make_failure_result()):
            run_main(payload)
        # 2回目: キャッシュヒットだがエラーなのでblock
        result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "FAILED" in parsed["reason"]

    def test_re_edit_invalidates_cache(self, tmp_path):
        """コード再編集でキャッシュが無効化され再実行される."""
        entries_v1 = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries_v1)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        # 1回目: 実行
        with mock.patch("subprocess.run", return_value=make_success_result()):
            run_main(payload)
        # ファイル再編集（新しいエントリ追加でedit_seqが変わる）
        entries_v2 = [
            make_entry([make_edit_block("/src/app.py")]),
            make_entry([make_bash_block("echo hello")]),
            make_entry([make_edit_block("/src/app.py")]),  # 再編集
        ]
        write_transcript(tmp_path, entries_v2)
        # 2回目: キャッシュ無効→再実行→block
        with mock.patch("subprocess.run", return_value=make_success_result()):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_failure_shows_error(self, tmp_path):
        """実行失敗時にエラー出力がblockメッセージに含まれる."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        with mock.patch("subprocess.run", return_value=make_failure_result()):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "FAILED" in parsed["reason"]
        assert "error" in parsed["reason"]

    def test_timeout_shows_in_output(self, tmp_path):
        """タイムアウト時にblockメッセージに表示される."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "timeout" in parsed["reason"]

    def test_command_not_found(self, tmp_path):
        """コマンド未発見時にblockメッセージに表示される."""
        entries = [make_entry([make_edit_block("/src/app.py")])]
        tp = write_transcript(tmp_path, entries)
        payload = {
            "tool_input": {"command": "git commit -m 'feat: add app'"},
            "transcript_path": str(tp),
        }
        err = FileNotFoundError()
        err.filename = "uv"
        with mock.patch("subprocess.run", side_effect=err):
            result = run_main(payload)
        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "uv" in parsed["reason"]
