"""Tests for block-magic-numbers.py hook."""

from pathlib import Path

from tests.conftest import run_hook_process

HOOK = str(Path(__file__).resolve().parent.parent / "hooks" / "block-magic-numbers.py")


def run_hook(file_path: str) -> dict[str, str] | None:
    """Run the hook against a file path."""
    return run_hook_process(
        HOOK,
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path},
        },
    )


class TestArgparseDetection:
    def test_integer_default_stops(self, tmp_path: Path) -> None:
        file_path = tmp_path / "cli.py"
        file_path.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--workers', default=3)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is not None
        assert result["decision"] == "stop"
        assert "default=3" in result["reason"]

    def test_float_default_stops(self, tmp_path: Path) -> None:
        file_path = tmp_path / "cli.py"
        file_path.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--ratio', default=0.5)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is not None
        assert result["decision"] == "stop"
        assert "default=0.5" in result["reason"]


class TestGeneralKwargDetection:
    def test_timeout_kwarg_stops(self, tmp_path: Path) -> None:
        file_path = tmp_path / "client.py"
        file_path.write_text(
            "import requests\n"
            "r = requests.get('http://example.com', timeout=30)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is not None
        assert result["decision"] == "stop"
        assert "timeout=30" in result["reason"]

    def test_retries_kwarg_stops(self, tmp_path: Path) -> None:
        file_path = tmp_path / "worker.py"
        file_path.write_text(
            "def run():\n"
            "    process(max_retries=5)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is not None
        assert result["decision"] == "stop"
        assert "max_retries=5" in result["reason"]

    def test_port_kwarg_stops(self, tmp_path: Path) -> None:
        file_path = tmp_path / "server.py"
        file_path.write_text(
            "app.run(host='0.0.0.0', port=8080)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is not None
        assert result["decision"] == "stop"
        assert "port=8080" in result["reason"]


class TestAllow:
    def test_named_constant_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "cli.py"
        file_path.write_text(
            "import argparse\n"
            "DEFAULT_WORKERS = 3\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--workers', default=DEFAULT_WORKERS)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_noqa_comment_skips_detection(self, tmp_path: Path) -> None:
        file_path = tmp_path / "cli.py"
        file_path.write_text(
            "requests.get(url, timeout=30)  # noqa: magic-number\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_safe_value_zero_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "app.py"
        file_path.write_text(
            "func(retries=0)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_safe_value_one_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "app.py"
        file_path.write_text(
            "func(count=1)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_enumerate_start_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "app.py"
        file_path.write_text(
            "for i, x in enumerate(items, start=2):\n"
            "    pass\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_range_stop_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "app.py"
        file_path.write_text(
            "list(range(stop=10))\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_bool_kwarg_is_allowed(self, tmp_path: Path) -> None:
        file_path = tmp_path / "app.py"
        file_path.write_text(
            "func(verbose=True)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_tests_directory_is_skipped(self, tmp_path: Path) -> None:
        file_path = tmp_path / "tests" / "cli.py"
        file_path.parent.mkdir()
        file_path.write_text(
            "requests.get(url, timeout=30)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_test_file_name_is_skipped(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test_cli.py"
        file_path.write_text(
            "requests.get(url, timeout=30)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None
