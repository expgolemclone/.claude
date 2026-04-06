"""Tests for hooks/project_root.py shared utility."""

import sys
from pathlib import Path

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
from project_root import find_git_root, find_project_root


class TestFindProjectRoot:
    def test_marker_in_same_dir(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").touch()
        assert find_project_root(str(tmp_path)) == str(tmp_path)

    def test_marker_in_parent(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").touch()
        sub = tmp_path / "src"
        sub.mkdir()
        assert find_project_root(str(sub)) == str(tmp_path)

    def test_no_marker(self, tmp_path: Path) -> None:
        sub = tmp_path / "isolated"
        sub.mkdir()
        assert find_project_root(str(sub)) is None

    def test_custom_marker(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").touch()
        sub = tmp_path / "pkg"
        sub.mkdir()
        assert find_project_root(str(sub), marker="go.mod") == str(tmp_path)

    def test_custom_marker_not_found(self, tmp_path: Path) -> None:
        sub = tmp_path / "isolated"
        sub.mkdir()
        assert find_project_root(str(sub), marker="go.mod") is None


class TestFindGitRoot:
    def test_git_dir_in_same_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert find_git_root(str(tmp_path)) == str(tmp_path)

    def test_git_file_in_parent(self, tmp_path: Path) -> None:
        (tmp_path / ".git").write_text("gitdir: /tmp/other\n", encoding="utf-8")
        sub = tmp_path / "src"
        sub.mkdir()
        assert find_git_root(str(sub)) == str(tmp_path)

    def test_git_root_not_found(self, tmp_path: Path) -> None:
        sub = tmp_path / "isolated"
        sub.mkdir()
        assert find_git_root(str(sub)) is None
