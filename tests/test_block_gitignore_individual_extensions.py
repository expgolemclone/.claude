"""Tests for block-gitignore-individual-extensions.py hook."""

from pathlib import Path

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-gitignore-individual-extensions.py")


def run_hook(tool_input: dict[str, str]) -> dict[str, str] | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block: individual file entries instead of wildcards
# ---------------------------------------------------------------------------

class TestBlock:
    def test_individual_py(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*\n!setup.py\n")
        result = run_hook({"file_path": str(gitignore)})
        assert result is not None
        assert result["decision"] == "block"
        assert "!*.py" in result["reason"]

    def test_individual_toml(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*\n!pyproject.toml\n")
        result = run_hook({"file_path": str(gitignore)})
        assert result is not None
        assert result["decision"] == "block"
        assert "!*.toml" in result["reason"]

    def test_multiple_violations(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*\n!setup.py\n!pyproject.toml\n")
        result = run_hook({"file_path": str(gitignore)})
        assert result is not None
        assert result["decision"] == "block"
        assert "!*.py" in result["reason"]
        assert "!*.toml" in result["reason"]


# ---------------------------------------------------------------------------
# Should allow: wildcard patterns or non-.gitignore files
# ---------------------------------------------------------------------------

class TestAllow:
    def test_wildcard_py_and_toml(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*\n!*.py\n!*.toml\n")
        assert run_hook({"file_path": str(gitignore)}) is None

    def test_not_gitignore(self, tmp_path: Path) -> None:
        other = tmp_path / "other.txt"
        other.write_text("!setup.py\n")
        assert run_hook({"file_path": str(other)}) is None

    def test_empty_file_path(self) -> None:
        assert run_hook({"file_path": ""}) is None

    def test_no_file_path_key(self) -> None:
        assert run_hook({}) is None

    def test_directory_patterns_ignored(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*\n!*.py\n!hooks/\n!hooks/**\n")
        assert run_hook({"file_path": str(gitignore)}) is None

    def test_comments_and_blanks_ignored(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# comment\n\n*\n!*.py\n!*.toml\n")
        assert run_hook({"file_path": str(gitignore)}) is None
