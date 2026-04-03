"""Tests for block-wildcard-versions.py hook."""

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-wildcard-versions.py")


def run_hook(tool_input: dict, tool_name: str = "Edit") -> dict | None:
    return run_hook_process(HOOK, {"tool_name": tool_name, "tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block
# ---------------------------------------------------------------------------


class TestBlock:
    def test_wildcard_version_double_quotes(self) -> None:
        result = run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": 'version = "*"',
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_wildcard_version_single_quotes(self) -> None:
        result = run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": "version = '*'",
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_wildcard_in_dependency(self) -> None:
        result = run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": '"flask", "*"',
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_write_tool(self) -> None:
        result = run_hook(
            {
                "file_path": "/tmp/project/pyproject.toml",
                "content": '[project]\nversion = "*"\n',
            },
            tool_name="Write",
        )
        assert result is not None
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------


class TestAllow:
    def test_specific_version(self) -> None:
        assert run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": 'version = ">=1.0,<2.0"',
        }) is None

    def test_glob_pattern(self) -> None:
        assert run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": 'include = ["*.py"]',
        }) is None

    def test_non_pyproject(self) -> None:
        assert run_hook({
            "file_path": "/tmp/project/setup.cfg",
            "new_string": 'version = "*"',
        }) is None

    def test_empty_content(self) -> None:
        assert run_hook({
            "file_path": "/tmp/project/pyproject.toml",
            "new_string": "",
        }) is None

    def test_no_path(self) -> None:
        assert run_hook({"new_string": 'version = "*"'}) is None
