"""Tests for block-settings-json-direct-edit.py hook."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR, SETTINGS_JSON
from tests.conftest import run_hook_process

HOOK = str(HOOKS_DIR / "block-settings-json-direct-edit.py")


def run_hook(tool_input: dict) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": tool_input})


# ---------------------------------------------------------------------------
# Should block
# ---------------------------------------------------------------------------

class TestBlock:
    def test_direct_path(self):
        result = run_hook({"file_path": str(SETTINGS_JSON)})
        assert result["decision"] == "block"

    def test_forward_slashes(self):
        result = run_hook({"file_path": str(SETTINGS_JSON).replace("\\", "/")})
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------

class TestAllow:
    def test_other_json_file(self):
        assert run_hook({"file_path": str(SETTINGS_JSON.parent / "other.json")}) is None

    def test_settings_json_different_dir(self):
        assert run_hook({"file_path": "/tmp/project/settings.json"}) is None

    def test_empty_file_path(self):
        assert run_hook({"file_path": ""}) is None

    def test_no_file_path_key(self):
        assert run_hook({}) is None
