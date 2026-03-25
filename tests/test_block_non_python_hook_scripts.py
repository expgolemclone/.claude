"""Tests for block-non-python-hook-scripts.py hook."""

import pytest

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-non-python-hook-scripts.py")
HOOKS_DIR_POSIX = str(HOOKS_DIR).replace("\\", "/")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block (non-Python in hooks/)
# ---------------------------------------------------------------------------

class TestBlock:
    def test_sh_in_hooks(self):
        result = run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.sh"})
        assert result["decision"] == "block"

    def test_js_in_hooks(self):
        result = run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.js"})
        assert result["decision"] == "block"

    def test_ts_in_hooks(self):
        result = run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.ts"})
        assert result["decision"] == "block"

    def test_bash_in_hooks(self):
        result = run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.bash"})
        assert result["decision"] == "block"

    def test_rb_in_hooks(self):
        result = run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.rb"})
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------

class TestAllow:
    def test_py_in_hooks(self):
        assert run_hook({"file_path": f"{HOOKS_DIR_POSIX}/myhook.py"}) is None

    def test_sh_outside_hooks(self):
        assert run_hook({"file_path": "/tmp/project/script.sh"}) is None

    def test_toml_in_hooks(self):
        assert run_hook({"file_path": f"{HOOKS_DIR_POSIX}/config.toml"}) is None

    def test_no_file_path(self):
        assert run_hook({}) is None
