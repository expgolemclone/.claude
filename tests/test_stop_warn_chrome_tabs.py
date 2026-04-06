"""Tests for stop-warn-chrome-tabs.py hook."""

import importlib
import io
import json
import subprocess
import sys
from unittest import mock

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("stop-warn-chrome-tabs")
main = mod.main


def run_main(stdin_data: dict[str, object]) -> str:
    """Run the hook main function with JSON stdin."""
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


class TestSkip:
    def test_stop_hook_active(self) -> None:
        with mock.patch.object(mod, "count_chrome_tabs", side_effect=AssertionError("unexpected call")):
            result = run_main({"stop_hook_active": True})

        assert result == ""

    def test_plan_mode(self) -> None:
        with mock.patch.object(mod, "count_chrome_tabs", side_effect=AssertionError("unexpected call")):
            result = run_main({"permission_mode": "plan"})

        assert result == ""


class TestDecision:
    def test_below_threshold_allows(self) -> None:
        with mock.patch.object(mod, "count_chrome_tabs", return_value=2):
            result = run_main({})

        assert result == ""

    def test_at_threshold_blocks(self) -> None:
        with mock.patch.object(mod, "count_chrome_tabs", return_value=3):
            result = run_main({})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "3 個" in parsed["reason"]

    def test_above_threshold_blocks(self) -> None:
        with mock.patch.object(mod, "count_chrome_tabs", return_value=5):
            result = run_main({})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "5 個" in parsed["reason"]


class TestCountChromeTabs:
    def test_non_zero_exit_returns_zero(self) -> None:
        fake_result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="",
        )

        with mock.patch("subprocess.run", return_value=fake_result):
            tab_count = mod.count_chrome_tabs()

        assert tab_count == 0

    def test_counts_renderer_lines(self) -> None:
        fake_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="123 chrome --type=renderer\n456 chrome --type=renderer\n",
            stderr="",
        )

        with mock.patch("subprocess.run", return_value=fake_result):
            tab_count = mod.count_chrome_tabs()

        assert tab_count == 2
