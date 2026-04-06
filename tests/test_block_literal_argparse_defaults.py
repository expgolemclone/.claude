"""Tests for block-literal-argparse-defaults.py hook."""

from pathlib import Path

from tests.conftest import run_hook_process

HOOK = str(Path(__file__).resolve().parent.parent / "hooks" / "block-literal-argparse-defaults.py")


def run_hook(file_path: str) -> dict[str, str] | None:
    """Run the hook against a file path."""
    return run_hook_process(
        HOOK,
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path},
        },
    )


class TestDetection:
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
        assert "L3: default=3" in result["reason"]

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
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--workers', default=3)  # noqa: literal-default\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_tests_directory_is_skipped(self, tmp_path: Path) -> None:
        file_path = tmp_path / "tests" / "cli.py"
        file_path.parent.mkdir()
        file_path.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--workers', default=3)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None

    def test_test_file_name_is_skipped(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test_cli.py"
        file_path.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--workers', default=3)\n",
            encoding="utf-8",
        )

        result = run_hook(str(file_path))

        assert result is None
