"""Tests for stop-scan-any-type.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("stop-scan-any-type")
main = mod.main


def run_main(stdin_data: dict) -> str:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


class TestSkip:
    def test_stop_hook_active(self) -> None:
        result = run_main({"stop_hook_active": True, "cwd": "/tmp"})
        assert result == ""

    def test_plan_mode(self) -> None:
        result = run_main({"permission_mode": "plan", "cwd": "/tmp"})
        assert result == ""


class TestScanDetection:
    def test_blocks_when_any_found(self, tmp_path: Path) -> None:
        py_file = tmp_path / "bad.py"
        py_file.write_text("from typing import Any\nx: Any = 1\n")

        result = run_main({"cwd": str(tmp_path)})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "bad.py" in parsed["reason"]

    def test_passes_when_no_any(self, tmp_path: Path) -> None:
        py_file = tmp_path / "good.py"
        py_file.write_text("x: int = 1\n")

        result = run_main({"cwd": str(tmp_path)})

        assert result == ""

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("Any type here\n")

        result = run_main({"cwd": str(tmp_path)})

        assert result == ""

    def test_scans_subdirectories(self, tmp_path: Path) -> None:
        sub = tmp_path / "pkg" / "sub"
        sub.mkdir(parents=True)
        py_file = sub / "nested.py"
        py_file.write_text("import typing\nx: typing.Any = 1\n")

        result = run_main({"cwd": str(tmp_path)})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "nested.py" in parsed["reason"]

    def test_reports_multiple_violations(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("from typing import Any\n")
        (tmp_path / "b.py").write_text("x: Any = 1\n")

        result = run_main({"cwd": str(tmp_path)})

        parsed = json.loads(result)
        assert parsed["decision"] == "block"
        assert "a.py" in parsed["reason"]
        assert "b.py" in parsed["reason"]

    def test_any_in_comment_only_still_detected(self, tmp_path: Path) -> None:
        py_file = tmp_path / "commented.py"
        py_file.write_text("# This uses Any\nx: int = 1\n")

        result = run_main({"cwd": str(tmp_path)})

        assert result == ""
