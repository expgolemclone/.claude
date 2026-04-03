"""Tests for block-missing-annotations.py hook."""

from tests.conftest import HOOKS_DIR, run_hook_process

HOOK = str(HOOKS_DIR / "block-missing-annotations.py")


def run_hook(tool_input: dict[str, str], tool_name: str = "Edit") -> dict[str, str] | None:
    return run_hook_process(HOOK, {"tool_name": tool_name, "tool_input": tool_input})


# ---------------------------------------------------------------------------
# Single-line: regression tests
# ---------------------------------------------------------------------------


class TestSingleLineBlock:
    def test_missing_param_annotation(self) -> None:
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(bar) -> None:\n    pass",
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_missing_return_annotation(self) -> None:
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(bar: int):\n    pass",
        })
        assert result is not None
        assert result["decision"] == "block"


class TestSingleLineAllow:
    def test_fully_annotated(self) -> None:
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(bar: int) -> None:\n    pass",
        }) is None

    def test_init_no_return(self) -> None:
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def __init__(self, bar: int):\n    pass",
        }) is None


# ---------------------------------------------------------------------------
# Multi-line: new coverage
# ---------------------------------------------------------------------------


class TestMultiLineBlock:
    def test_missing_param_annotation(self) -> None:
        code = (
            "def foo(\n"
            "    bar,\n"
            "    baz: str,\n"
            ") -> None:\n"
            "    pass\n"
        )
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_missing_return_annotation(self) -> None:
        code = (
            "def foo(\n"
            "    bar: int,\n"
            "    baz: str,\n"
            "):\n"
            "    pass\n"
        )
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_async_missing_param(self) -> None:
        code = (
            "async def fetch(\n"
            "    url,\n"
            ") -> str:\n"
            "    pass\n"
        )
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        })
        assert result is not None
        assert result["decision"] == "block"


class TestMultiLineAllow:
    def test_fully_annotated(self) -> None:
        code = (
            "def foo(\n"
            "    bar: int,\n"
            "    baz: str,\n"
            ") -> None:\n"
            "    pass\n"
        )
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        }) is None

    def test_self_cls_exempt(self) -> None:
        code = (
            "def method(\n"
            "    self,\n"
            "    bar: int,\n"
            ") -> None:\n"
            "    pass\n"
        )
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        }) is None

    def test_init_no_return(self) -> None:
        code = (
            "def __init__(\n"
            "    self,\n"
            "    bar: int,\n"
            "):\n"
            "    pass\n"
        )
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        }) is None

    def test_complex_type_annotations(self) -> None:
        code = (
            "def process(\n"
            "    items: list[dict[str, int]],\n"
            "    callback: Callable[[int], str],\n"
            ") -> None:\n"
            "    pass\n"
        )
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        }) is None


# ---------------------------------------------------------------------------
# Bug fixes: regression tests
# ---------------------------------------------------------------------------


class TestPositionalOnlyMarker:
    """Bug 1: `/` marker must not be flagged as missing annotation."""

    def test_slash_marker_single_line(self) -> None:
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(a: int, /, b: int) -> None:\n    pass",
        }) is None

    def test_slash_marker_multi_line(self) -> None:
        code = (
            "def foo(\n"
            "    a: int,\n"
            "    /,\n"
            "    b: int,\n"
            ") -> None:\n"
            "    pass\n"
        )
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        }) is None


class TestDefaultWithParens:
    """Bug 2: nested parens in defaults must not skip the entire function."""

    def test_tuple_default_missing_annotation(self) -> None:
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(bar=(1, 2)) -> None:\n    pass",
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_multi_line_tuple_default_missing_annotation(self) -> None:
        code = (
            "def foo(\n"
            "    bar=(1, 2),\n"
            ") -> None:\n"
            "    pass\n"
        )
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": code,
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_tuple_default_with_annotation(self) -> None:
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": "def foo(bar: tuple[int, ...] = (1, 2)) -> None:\n    pass",
        }) is None


class TestDefaultWithColon:
    """Bug 3: colon inside default value must not be mistaken for annotation."""

    def test_dict_default_missing_annotation(self) -> None:
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": 'def foo(bar={"a": 1}) -> None:\n    pass',
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_string_colon_default_missing_annotation(self) -> None:
        result = run_hook({
            "file_path": "/tmp/example.py",
            "new_string": 'def foo(sep=":") -> None:\n    pass',
        })
        assert result is not None
        assert result["decision"] == "block"

    def test_dict_default_with_annotation(self) -> None:
        assert run_hook({
            "file_path": "/tmp/example.py",
            "new_string": 'def foo(bar: dict[str, int] = {"a": 1}) -> None:\n    pass',
        }) is None
