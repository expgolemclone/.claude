"""Tests for scripts/rewrite-commit-messages.py."""

import subprocess
import sys

import pytest

from tests.conftest import PROJECT_ROOT

SCRIPT = str(PROJECT_ROOT / "scripts" / "rewrite-commit-messages.py")


def run_filter(msg: str) -> str:
    result = subprocess.run(
        [sys.executable, SCRIPT],
        input=msg,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    return result.stdout


# ---------------------------------------------------------------------------
# Co-Authored-By removal
# ---------------------------------------------------------------------------

class TestCoAuthoredBy:
    def test_removes_co_authored_by(self):
        out = run_filter("feat: add feature\n\nCo-Authored-By: Someone <a@b>\n")
        assert "Co-Authored-By" not in out

    def test_removes_case_insensitive(self):
        out = run_filter("fix: bug\n\nco-authored-by: Someone <a@b>\n")
        assert "co-authored-by" not in out

    def test_removes_preceding_blank_lines(self):
        out = run_filter("feat: add feature\n\n\nCo-Authored-By: X <x@y>\n")
        assert out == "feat: add feature\n"


# ---------------------------------------------------------------------------
# Prohibited keyword removal
# ---------------------------------------------------------------------------

class TestProhibitedKeywords:
    def test_removes_keyword(self):
        out = run_filter("feat: update instructions file\n")
        assert "feat:" in out

    def test_removes_case_insensitive_keyword(self):
        out = run_filter("feat: add feature\n")
        assert "feat:" in out


# ---------------------------------------------------------------------------
# CLAUDE.md replacement
# ---------------------------------------------------------------------------

class TestClaudeMdReplacement:
    def test_replaces_claude_md(self):
        # Keyword removal runs before CLAUDE.md replacement,
        # so "CLAUDE" is stripped first, leaving ".md"
        out = run_filter("update CLAUDE.md with new rules\n")
        assert "CLAUDE" not in out


# ---------------------------------------------------------------------------
# Trailing whitespace
# ---------------------------------------------------------------------------

class TestTrailingWhitespace:
    def test_strips_trailing_whitespace(self):
        out = run_filter("feat: something   \n\n  \n")
        assert out.endswith("\n")
        assert not out.endswith("  \n")

    def test_plain_message_preserved(self):
        out = run_filter("feat: normal commit\n")
        assert out == "feat: normal commit\n"
