"""Tests for stop-require-source-verification.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("stop-require-source-verification")
main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user_text(text: str = "Hello") -> dict:
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def make_user_tool_result(tool_use_id: str = "tu_1") -> dict:
    return {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "tool_use_id": tool_use_id}]},
    }


def make_assistant_text(text: str = "response") -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def make_assistant_tool_use(name: str = "Read", tool_id: str = "tu_1") -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name}]},
    }


def make_progress() -> dict:
    return {"type": "progress", "message": {"content": "thinking..."}}


def write_transcript(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return p


def run_main(stdin_data: dict) -> str:
    """Run main() with mocked stdin/stdout, return stdout content."""
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


def make_stdin(
    transcript_path: str = "",
    last_assistant_message: str = "x" * 250,
    stop_hook_active: bool = False,
) -> dict:
    d: dict = {
        "last_assistant_message": last_assistant_message,
        "transcript_path": transcript_path,
    }
    if stop_hook_active:
        d["stop_hook_active"] = True
    return d


# ---------------------------------------------------------------------------
# Early returns (should NOT block)
# ---------------------------------------------------------------------------

class TestEarlyReturns:
    def test_1_stop_hook_active(self, tmp_path):
        tp = write_transcript(tmp_path, [make_user_text(), make_assistant_text("a" * 300)])
        result = run_main(make_stdin(str(tp), "a" * 300, stop_hook_active=True))
        assert result == ""

    def test_3_empty_transcript_path(self):
        result = run_main(make_stdin(transcript_path="", last_assistant_message="a" * 250))
        assert result == ""

    def test_4_no_user_entry(self, tmp_path):
        tp = write_transcript(tmp_path, [make_assistant_text("a" * 300)])
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""


# ---------------------------------------------------------------------------
# Core transcript logic
# ---------------------------------------------------------------------------

class TestTranscriptParsing:
    def test_5_web_search_allows(self, tmp_path):
        entries = [
            make_user_text(),
            make_assistant_tool_use("WebSearch"),
            make_user_tool_result(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_5b_coding_tool_allows(self, tmp_path: Path) -> None:
        """Coding tools (Read, Edit, Bash, etc.) indicate a coding task — no block."""
        entries = [
            make_user_text(),
            make_assistant_tool_use("Read"),
            make_user_tool_result(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_5c_non_coding_non_search_tool_blocks(self, tmp_path: Path) -> None:
        """Tools that are neither search nor coding should still block."""
        entries = [
            make_user_text(),
            make_assistant_tool_use("SomeOtherTool"),
            make_user_tool_result(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    @pytest.mark.parametrize("tool", ["Edit", "Write", "Bash", "Grep", "Glob", "NotebookEdit"])
    def test_5d_each_coding_tool_allows(self, tmp_path: Path, tool: str) -> None:
        entries = [
            make_user_text(),
            make_assistant_tool_use(tool),
            make_user_tool_result(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_6_no_tool_use_blocks(self, tmp_path):
        entries = [
            make_user_text(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_7_multiple_search_tools(self, tmp_path):
        entries = [
            make_user_text(),
            make_assistant_tool_use("WebSearch", "tu_1"),
            make_user_tool_result("tu_1"),
            make_assistant_tool_use("WebFetch", "tu_2"),
            make_user_tool_result("tu_2"),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_8_tool_result_only_user_skipped(self, tmp_path):
        """tool_result-only user entries should be skipped; find the real user before them."""
        entries = [
            make_user_text("real question"),
            make_assistant_tool_use("WebSearch", "tu_1"),
            make_user_tool_result("tu_1"),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_9_empty_transcript_file(self, tmp_path):
        tp = tmp_path / "empty.jsonl"
        tp.write_text("")
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_10_invalid_json_lines(self, tmp_path):
        tp = tmp_path / "mixed.jsonl"
        lines = [
            "NOT VALID JSON",
            json.dumps(make_user_text()),
            "{broken",
            json.dumps(make_assistant_text("a" * 300)),
        ]
        tp.write_text("\n".join(lines) + "\n")
        result = run_main(make_stdin(str(tp), "a" * 300))
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_11_mixed_content_user(self, tmp_path):
        """User message with both tool_result and text should be treated as real user."""
        mixed_user = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1"},
                    {"type": "text", "text": "and also this question"},
                ]
            },
        }
        entries = [
            mixed_user,
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        parsed = json.loads(result)
        assert parsed["decision"] == "block"

    def test_12_progress_entries_ignored(self, tmp_path):
        entries = [
            make_user_text(),
            make_progress(),
            make_assistant_tool_use("WebSearch"),
            make_progress(),
            make_user_tool_result(),
            make_assistant_text("a" * 300),
        ]
        tp = write_transcript(tmp_path, entries)
        result = run_main(make_stdin(str(tp), "a" * 300))
        assert result == ""

    def test_14_transcript_file_not_found(self):
        result = run_main(make_stdin("/nonexistent/path/transcript.jsonl", "a" * 300))
        assert result == ""
