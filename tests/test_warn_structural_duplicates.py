"""Tests for warn-structural-duplicates.py hook."""

import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
core = importlib.import_module("structural_clone_core")
mod = importlib.import_module("warn-structural-duplicates")
main = mod.main


def run_main(stdin_data: dict[str, object]) -> str:
    """Run the hook main with patched stdio."""
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


def write_file(path: Path, content: str) -> None:
    """Write UTF-8 test content."""
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for hook tests."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    return tmp_path


class TestSkip:
    def test_non_python_file(self) -> None:
        result = run_main({"tool_input": {"file_path": "/tmp/example.txt"}})
        assert result == ""

    def test_no_git_root(self, tmp_path: Path) -> None:
        file_path = tmp_path / "solo.py"
        write_file(file_path, "def one() -> None:\n    pass\n")

        result = run_main({"tool_input": {"file_path": str(file_path)}})

        assert result == ""


class TestDetection:
    def test_stop_for_structural_duplicate(self, git_repo: Path) -> None:
        first_file = git_repo / "alpha.py"
        second_file = git_repo / "beta.py"
        write_file(
            first_file,
            (
                "def _cmd_fetch_prices(args: object) -> None:\n"
                "    pool = _resolve_proxy_pool(args)\n"
                "    conn = get_connection()\n"
                "    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n"
                "    dispatch_workers(tickers, pool, worker_fn=fetch_prices_worker, label='prices')\n"
            ),
        )
        write_file(
            second_file,
            (
                "def _run_scrape_workers(args: object, worker_fn: object, label: str) -> None:\n"
                "    pool = _resolve_proxy_pool(args)\n"
                "    conn = get_connection()\n"
                "    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n"
                "    dispatch_workers(tickers, pool, worker_fn=worker_fn, label=label)\n"
            ),
        )
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "初期状態"], cwd=git_repo, check=True, capture_output=True, text=True)

        third_file = git_repo / "gamma.py"
        write_file(
            third_file,
            (
                "def run_candidate(args: object, worker_fn: object, label: str) -> None:\n"
                "    pool = _resolve_proxy_pool(args)\n"
                "    conn = get_connection()\n"
                "    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n"
                "    dispatch_workers(tickers, pool, worker_fn=worker_fn, label=label)\n"
            ),
        )

        result = run_main({"tool_input": {"file_path": str(third_file)}})

        parsed = json.loads(result)
        assert parsed["decision"] == "stop"
        assert "run_candidate" in parsed["reason"]
        assert "_run_scrape_workers" in parsed["reason"]

    def test_small_function_is_ignored(self, git_repo: Path) -> None:
        first_file = git_repo / "alpha.py"
        second_file = git_repo / "beta.py"
        write_file(
            first_file,
            (
                "def one(value: int) -> int:\n"
                "    result = value + 1\n"
                "    return result\n"
            ),
        )
        write_file(
            second_file,
            (
                "def two(value: int) -> int:\n"
                "    result = value + 1\n"
                "    return result\n"
            ),
        )
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "初期状態"], cwd=git_repo, check=True, capture_output=True, text=True)

        third_file = git_repo / "gamma.py"
        write_file(
            third_file,
            (
                "def three(value: int) -> int:\n"
                "    result = value + 1\n"
                "    return result\n"
            ),
        )

        result = run_main({"tool_input": {"file_path": str(third_file)}})

        assert result == ""


class TestCache:
    def test_cache_invalidates_on_hash_change(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        source_path = tmp_path / "sample.py"
        write_file(source_path, "def sample(value: int) -> int:\n    return value\n")

        initial_cache = core.build_cache_payload(
            schema_version="1",
            repo_root=str(tmp_path),
            records_by_file={
                str(source_path): [
                    {
                        "path": str(source_path),
                        "qualname": "sample",
                        "lineno": 1,
                        "end_lineno": 2,
                        "stmt_count": 1,
                        "ast_node_count": 10,
                        "vector": {"Name:sample": 1.0},
                        "normalized_tree": {"label": "FunctionDef", "children": []},
                    }
                ]
            },
        )
        core.save_cache(cache_path, initial_cache)

        loaded = core.load_cache(cache_path)
        stale_records = core.get_cached_records_for_file(loaded, source_path)
        assert stale_records is not None

        write_file(source_path, "def sample(value: int) -> int:\n    return value + 1\n")

        loaded_after = core.load_cache(cache_path)
        assert core.get_cached_records_for_file(loaded_after, source_path) is None
