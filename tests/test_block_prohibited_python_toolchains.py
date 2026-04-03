"""Tests for block-prohibited-python-toolchains.py hook."""

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-prohibited-python-toolchains.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block: prohibited toolchains
# ---------------------------------------------------------------------------


class TestBlockProhibitedTools:
    @pytest.mark.parametrize("tool", ["pyenv", "conda", "pipenv", "poetry"])
    def test_direct_command(self, tool: str) -> None:
        result = run_hook({"command": f"{tool} install something"})
        assert result is not None
        assert result["decision"] == "block"
        assert tool in result["reason"]

    def test_after_and(self) -> None:
        result = run_hook({"command": "cd /tmp && conda install numpy"})
        assert result is not None
        assert result["decision"] == "block"

    def test_after_semicolon(self) -> None:
        result = run_hook({"command": "echo hello; poetry add flask"})
        assert result is not None
        assert result["decision"] == "block"

    def test_after_pipe(self) -> None:
        result = run_hook({"command": "echo | pipenv install"})
        assert result is not None
        assert result["decision"] == "block"

    def test_in_subshell(self) -> None:
        result = run_hook({"command": "echo $(conda env list)"})
        assert result is not None
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should block: bare pip / pip3
# ---------------------------------------------------------------------------


class TestBlockPip:
    def test_pip_install(self) -> None:
        result = run_hook({"command": "pip install numpy"})
        assert result is not None
        assert result["decision"] == "block"

    def test_pip3_install(self) -> None:
        result = run_hook({"command": "pip3 install numpy"})
        assert result is not None
        assert result["decision"] == "block"

    def test_pip_after_separator(self) -> None:
        result = run_hook({"command": "cd /app && pip install -r req.txt"})
        assert result is not None
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow: uv pip
# ---------------------------------------------------------------------------


class TestAllowUvPip:
    def test_uv_pip_install(self) -> None:
        assert run_hook({"command": "uv pip install numpy"}) is None

    def test_uv_pip_compile(self) -> None:
        assert run_hook({"command": "uv pip compile requirements.in"}) is None

    def test_uv_add(self) -> None:
        assert run_hook({"command": "uv add requests"}) is None


# ---------------------------------------------------------------------------
# Should allow: read-only / unrelated
# ---------------------------------------------------------------------------


class TestAllow:
    def test_grep_for_tool(self) -> None:
        assert run_hook({"command": "grep pyenv .bashrc"}) is None

    def test_which_pip(self) -> None:
        assert run_hook({"command": "which pip"}) is None

    def test_tool_in_quoted_string(self) -> None:
        assert run_hook({"command": 'echo "use conda instead"'}) is None

    def test_empty_command(self) -> None:
        assert run_hook({"command": ""}) is None

    def test_no_command(self) -> None:
        assert run_hook({}) is None

    def test_unrelated_command(self) -> None:
        assert run_hook({"command": "ls -la"}) is None
