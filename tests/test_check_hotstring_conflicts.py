"""Tests for check-hotstring-conflicts.py hook."""

import importlib
import sys

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("check-hotstring-conflicts")
extract_hotstrings = mod.extract_hotstrings
find_prefix_conflicts = mod.find_prefix_conflicts
find_ahk_files = mod.find_ahk_files


# ---------------------------------------------------------------------------
# extract_hotstrings
# ---------------------------------------------------------------------------

class TestExtractHotstrings:
    def test_simple_hotstring(self, tmp_path):
        f = tmp_path / "test.ahk"
        f.write_text("::btw::by the way\n", encoding="utf-8")
        result = extract_hotstrings(f)
        assert len(result) == 1
        assert result[0][0] == "btw"
        assert result[0][2] == 1

    def test_multiple_hotstrings(self, tmp_path):
        f = tmp_path / "test.ahk"
        f.write_text("::abc::Alpha\n; comment\n::def::Delta\n", encoding="utf-8")
        result = extract_hotstrings(f)
        assert len(result) == 2
        assert result[0][0] == "abc"
        assert result[1][0] == "def"

    def test_with_options(self, tmp_path):
        f = tmp_path / "test.ahk"
        f.write_text(":*:teh::the\n", encoding="utf-8")
        result = extract_hotstrings(f)
        assert len(result) == 1
        assert result[0][0] == "teh"

    def test_no_hotstrings(self, tmp_path):
        f = tmp_path / "test.ahk"
        f.write_text("; just a comment\nMsgBox Hello\n", encoding="utf-8")
        assert extract_hotstrings(f) == []

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.ahk"
        assert extract_hotstrings(f) == []


# ---------------------------------------------------------------------------
# find_prefix_conflicts
# ---------------------------------------------------------------------------

class TestFindPrefixConflicts:
    def test_no_conflict(self):
        hs = [("abc", "f1", 1), ("def", "f1", 2)]
        assert find_prefix_conflicts(hs) == []

    def test_prefix_conflict(self):
        hs = [("ab", "f1", 1), ("abc", "f1", 2)]
        conflicts = find_prefix_conflicts(hs)
        assert len(conflicts) == 1
        assert conflicts[0][0][0] == "ab"
        assert conflicts[0][1][0] == "abc"

    def test_reverse_order_still_detected(self):
        hs = [("abc", "f1", 1), ("ab", "f1", 2)]
        conflicts = find_prefix_conflicts(hs)
        assert len(conflicts) == 1
        assert conflicts[0][0][0] == "ab"

    def test_identical_triggers_no_conflict(self):
        hs = [("abc", "f1", 1), ("abc", "f2", 2)]
        assert find_prefix_conflicts(hs) == []

    def test_empty_list(self):
        assert find_prefix_conflicts([]) == []

    def test_multiple_conflicts(self):
        hs = [("a", "f1", 1), ("ab", "f1", 2), ("abc", "f1", 3)]
        conflicts = find_prefix_conflicts(hs)
        assert len(conflicts) == 3  # a<ab, a<abc, ab<abc


# ---------------------------------------------------------------------------
# find_ahk_files
# ---------------------------------------------------------------------------

class TestFindAhkFiles:
    def test_finds_ahk_files(self, tmp_path):
        (tmp_path / "a.ahk").write_text("", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.ahk").write_text("", encoding="utf-8")
        result = find_ahk_files(tmp_path)
        assert len(result) == 2

    def test_excludes_dot_dirs(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "c.ahk").write_text("", encoding="utf-8")
        (tmp_path / "a.ahk").write_text("", encoding="utf-8")
        result = find_ahk_files(tmp_path)
        assert len(result) == 1

    def test_empty_dir(self, tmp_path):
        assert find_ahk_files(tmp_path) == []
