"""Tests for warn-hardcoded-paths hook."""

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

HOOK_SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "warn-hardcoded-paths.py"


def run_hook(file_path: str, tool_name: str = "Write") -> dict | None:
    """Run the hook with given file_path and return parsed JSON output or None."""
    stdin_data = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    })
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def make_py_file(content: str) -> str:
    """Create a temporary .py file with given content and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    f.write(textwrap.dedent(content))
    f.close()
    return f.name


class TestDetection:
    """ハードコードパスを検出すべきケース。"""

    def test_unix_home_path(self):
        path = make_py_file('data = "/home/user/data.csv"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_unix_etc_path(self):
        path = make_py_file('config = "/etc/myapp/config.yml"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_unix_var_path(self):
        path = make_py_file('log_dir = "/var/log/myapp"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_unix_usr_path(self):
        path = make_py_file('bin_path = "/usr/local/bin/tool"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_unix_opt_path(self):
        path = make_py_file('app_dir = "/opt/myapp/bin"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_unix_tmp_path(self):
        path = make_py_file('tmp = "/tmp/workdir"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_windows_backslash_path(self):
        path = make_py_file('data = "C:\\\\Users\\\\foo\\\\bar"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_windows_forward_slash_path(self):
        path = make_py_file('data = "C:/Users/foo/bar"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"

    def test_windows_lowercase_drive(self):
        path = make_py_file('path = "d:/projects/app"\n')
        result = run_hook(path)
        assert result is not None
        assert result["decision"] == "stop"


class TestExclusion:
    """除外すべきケース。"""

    def test_shebang_line(self):
        path = make_py_file('#!/usr/bin/env python3\nprint("hello")\n')
        result = run_hook(path)
        assert result is None

    def test_comment_line(self):
        path = make_py_file('# config is at /etc/myapp/config.yml\nprint("hello")\n')
        result = run_hook(path)
        assert result is None

    def test_indented_comment(self):
        path = make_py_file('    # see /home/user/docs\nprint("hello")\n')
        result = run_hook(path)
        assert result is None

    def test_import_line(self):
        path = make_py_file('import os\nfrom pathlib import Path\n')
        result = run_hook(path)
        assert result is None

    def test_dynamic_path_dunder_file(self):
        path = make_py_file('base = os.path.dirname(__file__)\n')
        result = run_hook(path)
        assert result is None

    def test_dynamic_path_pathlib(self):
        path = make_py_file('base = Path(__file__).parent\n')
        result = run_hook(path)
        assert result is None

    def test_non_py_file(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write('/home/user/data.csv\n')
        f.close()
        result = run_hook(f.name)
        assert result is None

    def test_clean_file(self):
        path = make_py_file('from pathlib import Path\nx = Path(__file__).parent / "data.csv"\n')
        result = run_hook(path)
        assert result is None
