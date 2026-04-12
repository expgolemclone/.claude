#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): enforce scrape interval >= 1.0s.

Files under scrape/ directories must respect the minimum request interval
defined in config/common.toml [scrape.manners].  This hook checks:

- TOML: ``interval`` key must exist and be >= 1.0s
- Python: AST-based sleep value check
- Rust / JS / TS / Dart: regex-based sleep value + HTTP call check
"""

import ast
import json
import os
import re
import sys
import tomllib

_MIN_INTERVAL = 1.0

_NOQA_RE = re.compile(r"(?:#|//)\s*noqa:\s*scrape-interval")


# -- Language definitions for regex-based checks --

_SleepPattern = tuple[re.Pattern[str], int, str]  # (regex, capture group, "s"|"ms")


class _LangDef:
    __slots__ = ("http_re", "sleep_patterns")

    def __init__(
        self,
        http_re: re.Pattern[str],
        sleep_patterns: list[_SleepPattern],
    ) -> None:
        self.http_re = http_re
        self.sleep_patterns = sleep_patterns


_PYTHON_HTTP_RE = re.compile(
    r"\b(?:requests|httpx|session|client)\."
    r"(?:get|post|put|patch|delete|head|options|request|send)\b"
    r"|\baiohttp\.ClientSession\b"
    r"|\bpage\.goto\b"
    r"|\burllib\.request\.urlopen\b"
)

_RUST = _LangDef(
    http_re=re.compile(
        r"\breqwest::(?:get|Client)\b"
        r"|\bclient\.(?:get|post|put|patch|delete|head|request)\("
        r"|\.send\(\)\.await\b"
        r"|\bhyper::Client\b"
        r"|\bsurf::(?:get|post|put|delete)\b"
    ),
    sleep_patterns=[
        (re.compile(r"Duration::from_secs\(\s*(\d+)"), 1, "s"),
        (re.compile(r"Duration::from_secs_f(?:32|64)\(\s*([\d.]+)"), 1, "s"),
        (re.compile(r"Duration::from_millis\(\s*(\d+)"), 1, "ms"),
    ],
)

_JS_TS = _LangDef(
    http_re=re.compile(
        r"\bfetch\("
        r"|\baxios\.(?:get|post|put|patch|delete|head|request)\("
        r"|\bgot\("
        r"|\bpage\.goto\("
        r"|\bky\.(?:get|post|put|patch|delete|head)\("
    ),
    sleep_patterns=[
        (re.compile(r"setTimeout\([^,]+,\s*(\d+)"), 1, "ms"),
        (re.compile(r"(?:sleep|delay)\(\s*(\d+)"), 1, "ms"),
        (re.compile(r"waitForTimeout\(\s*(\d+)"), 1, "ms"),
    ],
)

_DART = _LangDef(
    http_re=re.compile(
        r"\bhttp\.(?:get|post|put|patch|delete|head|read)\("
        r"|\bclient\.(?:get|post|put|patch|delete|head|send)\("
        r"|\bDio\(\)"
    ),
    sleep_patterns=[
        (re.compile(r"Duration\(\s*seconds:\s*(\d+)"), 1, "s"),
        (re.compile(r"Duration\(\s*milliseconds:\s*(\d+)"), 1, "ms"),
    ],
)

_EXT_TO_LANG: dict[str, _LangDef] = {
    ".rs": _RUST,
    ".js": _JS_TS,
    ".ts": _JS_TS,
    ".dart": _DART,
}


def _is_scrape_file(file_path: str) -> bool:
    """Return True if file is under a scrape/ directory."""
    norm = file_path.replace("\\", "/")
    return "/scrape/" in norm or norm.startswith("scrape/")


def _is_test_file(file_path: str) -> bool:
    norm = file_path.replace("\\", "/")
    return "/tests/" in norm or os.path.basename(file_path).startswith("test_")


def _parse_interval_str(value: str) -> float | None:
    """Parse interval strings like '1.0s', '500ms', '2s' into seconds."""
    value = value.strip()
    if value.endswith("ms"):
        try:
            return float(value[:-2]) / 1000.0
        except ValueError:
            return None
    if value.endswith("s"):
        try:
            return float(value[:-1])
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


# -- TOML checks --


def _check_toml(file_path: str) -> str | None:
    """Check a TOML file for interval compliance.  Returns reason or None."""
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    interval_value = _find_interval_in_dict(data)
    if interval_value is None:
        return (
            f"{os.path.basename(file_path)}: interval キーが定義されていません。\n"
            f"scrape設定には interval >= {_MIN_INTERVAL}s を含めてください。"
        )

    seconds = _resolve_interval(interval_value)
    if seconds is None:
        return (
            f"{os.path.basename(file_path)}: interval の値を解析できません: {interval_value!r}"
        )

    if seconds < _MIN_INTERVAL:
        return (
            f"{os.path.basename(file_path)}: interval = {interval_value!r} ({seconds}s) "
            f"は最低 {_MIN_INTERVAL}s 未満です。"
        )

    return None


def _find_interval_in_dict(data: dict) -> object | None:
    """Recursively search for an 'interval' key in nested dicts."""
    if "interval" in data:
        return data["interval"]
    for v in data.values():
        if isinstance(v, dict):
            result = _find_interval_in_dict(v)
            if result is not None:
                return result
    return None


def _resolve_interval(value: object) -> float | None:
    """Convert an interval value (str or number) to seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return _parse_interval_str(value)
    return None


# -- Regex-based checks (Rust / JS / TS / Dart) --


def _check_regex_lang(file_path: str, lang: _LangDef) -> str | None:
    """Check a source file using regex patterns.  Returns reason or None."""
    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()
    basename = os.path.basename(file_path)

    low_sleeps = _find_low_sleeps_regex(lines, lang.sleep_patterns)
    if low_sleeps:
        details = "\n".join(f"  L{ln}: {text}" for ln, text in low_sleeps)
        return (
            f"{basename}: sleep/delay の値が {_MIN_INTERVAL}s 未満です。\n"
            f"{details}\n"
            f"リクエスト間隔を {_MIN_INTERVAL}s 以上にしてください "
            f"(// noqa: scrape-interval で除外可)。"
        )

    has_http = _has_http_regex(lines, lang.http_re)
    if has_http and not _has_adequate_sleep_regex(lines, lang.sleep_patterns):
        return (
            f"{basename}: HTTP呼び出しがありますが "
            f"sleep >= {_MIN_INTERVAL}s が見つかりません。\n"
            f"リクエスト間隔を確保する sleep/delay を追加してください "
            f"(// noqa: scrape-interval で除外可)。"
        )

    return None


def _find_low_sleeps_regex(
    lines: list[str], patterns: list[_SleepPattern]
) -> list[tuple[int, str]]:
    """Return (lineno, matched_text) for sleep calls below threshold."""
    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, 1):
        if _NOQA_RE.search(line):
            continue
        for pat, group, unit in patterns:
            m = pat.search(line)
            if m is None:
                continue
            try:
                value = float(m.group(group))
            except (ValueError, IndexError):
                continue
            seconds = value / 1000.0 if unit == "ms" else value
            if seconds < _MIN_INTERVAL:
                violations.append((lineno, line.strip()))
                break
    return violations


def _has_http_regex(lines: list[str], http_re: re.Pattern[str]) -> bool:
    for line in lines:
        if _NOQA_RE.search(line):
            continue
        if http_re.search(line):
            return True
    return False


def _has_adequate_sleep_regex(
    lines: list[str], patterns: list[_SleepPattern]
) -> bool:
    for line in lines:
        for pat, group, unit in patterns:
            m = pat.search(line)
            if m is None:
                continue
            try:
                value = float(m.group(group))
            except (ValueError, IndexError):
                continue
            seconds = value / 1000.0 if unit == "ms" else value
            if seconds >= _MIN_INTERVAL:
                return True
    return False


# -- Python checks --


def _check_python(file_path: str) -> str | None:
    """Check a Python file for interval compliance.  Returns reason or None."""
    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    lines = source.splitlines()

    # Check 1: sleep calls with value < _MIN_INTERVAL
    low_sleeps = _find_low_sleep_calls(source, lines)
    if low_sleeps:
        details = "\n".join(
            f"  L{lineno}: {call}({value})" for lineno, call, value in low_sleeps
        )
        return (
            f"{os.path.basename(file_path)}: sleep の値が {_MIN_INTERVAL}s 未満です。\n"
            f"{details}\n"
            f"リクエスト間隔を {_MIN_INTERVAL}s 以上にしてください "
            f"(# noqa: scrape-interval で除外可)。"
        )

    # Check 2: HTTP calls present but no adequate sleep anywhere
    has_http = _has_http_calls(source, lines)
    if has_http and not _has_adequate_sleep(source):
        return (
            f"{os.path.basename(file_path)}: HTTP呼び出しがありますが "
            f"sleep >= {_MIN_INTERVAL}s が見つかりません。\n"
            f"リクエスト間隔を確保する sleep を追加してください "
            f"(# noqa: scrape-interval で除外可)。"
        )

    return None


def _find_low_sleep_calls(
    source: str, lines: list[str]
) -> list[tuple[int, str, float]]:
    """Return (lineno, func_name, value) for sleep calls with value < min."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations: list[tuple[int, str, float]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _get_sleep_func_name(node.func)
        if func_name is None:
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, (int, float)):
            continue
        if isinstance(arg.value, bool):
            continue
        value = float(arg.value)
        if value >= _MIN_INTERVAL:
            continue
        line = lines[node.lineno - 1]
        if _NOQA_RE.search(line):
            continue
        violations.append((node.lineno, func_name, value))

    return violations


def _get_sleep_func_name(func: ast.expr) -> str | None:
    """Return 'time.sleep' or 'asyncio.sleep' if the call matches, else None."""
    if isinstance(func, ast.Attribute) and func.attr == "sleep":
        if isinstance(func.value, ast.Name) and func.value.id in ("time", "asyncio"):
            return f"{func.value.id}.sleep"
    if isinstance(func, ast.Name) and func.id == "sleep":
        return "sleep"
    return None


def _has_http_calls(source: str, lines: list[str]) -> bool:
    """Return True if the source contains HTTP request patterns."""
    for line in lines:
        if _NOQA_RE.search(line):
            continue
        if _PYTHON_HTTP_RE.search(line):
            return True
    return False


def _has_adequate_sleep(source: str) -> bool:
    """Return True if at least one sleep >= _MIN_INTERVAL exists."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _get_sleep_func_name(node.func) is None:
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
            if not isinstance(arg.value, bool) and float(arg.value) >= _MIN_INTERVAL:
                return True
    return False


# -- Entry point --


def main() -> None:
    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not _is_scrape_file(file_path):
        return

    if _is_test_file(file_path):
        return

    if not os.path.isfile(file_path):
        return

    reason: str | None = None
    ext = os.path.splitext(file_path)[1]
    if ext == ".toml":
        reason = _check_toml(file_path)
    elif ext == ".py":
        reason = _check_python(file_path)
    elif ext in _EXT_TO_LANG:
        reason = _check_regex_lang(file_path, _EXT_TO_LANG[ext])

    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
