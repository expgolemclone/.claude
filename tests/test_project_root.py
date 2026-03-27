"""Tests for hooks/project_root.py shared utility."""

import sys

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
from project_root import find_project_root


class TestFindProjectRoot:
    def test_marker_in_same_dir(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        assert find_project_root(str(tmp_path)) == str(tmp_path)

    def test_marker_in_parent(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        sub = tmp_path / "src"
        sub.mkdir()
        assert find_project_root(str(sub)) == str(tmp_path)

    def test_no_marker(self, tmp_path):
        sub = tmp_path / "isolated"
        sub.mkdir()
        assert find_project_root(str(sub)) is None

    def test_custom_marker(self, tmp_path):
        (tmp_path / "go.mod").touch()
        sub = tmp_path / "pkg"
        sub.mkdir()
        assert find_project_root(str(sub), marker="go.mod") == str(tmp_path)

    def test_custom_marker_not_found(self, tmp_path):
        sub = tmp_path / "isolated"
        sub.mkdir()
        assert find_project_root(str(sub), marker="go.mod") is None
