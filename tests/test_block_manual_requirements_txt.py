"""Tests for block-manual-requirements-txt.py hook."""

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-manual-requirements-txt.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block
# ---------------------------------------------------------------------------


class TestBlock:
    def test_requirements_txt(self) -> None:
        result = run_hook({"file_path": "/tmp/project/requirements.txt"})
        assert result is not None
        assert result["decision"] == "block"

    def test_requirements_dev_txt(self) -> None:
        result = run_hook({"file_path": "/tmp/project/requirements-dev.txt"})
        assert result is not None
        assert result["decision"] == "block"

    def test_requirements_lock_txt(self) -> None:
        result = run_hook({"file_path": "/tmp/project/requirements.lock.txt"})
        assert result is not None
        assert result["decision"] == "block"

    def test_nested_requirements(self) -> None:
        result = run_hook({"file_path": "/home/user/app/requirements.txt"})
        assert result is not None
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------


class TestAllow:
    def test_pyproject_toml(self) -> None:
        assert run_hook({"file_path": "/tmp/project/pyproject.toml"}) is None

    def test_requirements_in(self) -> None:
        assert run_hook({"file_path": "/tmp/project/requirements.in"}) is None

    def test_unrelated_txt(self) -> None:
        assert run_hook({"file_path": "/tmp/project/notes.txt"}) is None

    def test_empty_path(self) -> None:
        assert run_hook({"file_path": ""}) is None

    def test_no_path(self) -> None:
        assert run_hook({}) is None
