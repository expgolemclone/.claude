#!/usr/bin/env python3
"""PreToolUse hook: auto-execute unverified code before git commit.

On first commit attempt, runs all unverified scripts in parallel and blocks
with the output for review. On second attempt (cache hit), approves.
"""

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import NamedTuple

from project_root import find_project_root

# 検証対象とする拡張子（実行可能なコードファイルのみ）
_CODE_EXTENSIONS = {".py", ".go", ".rs", ".c", ".cpp", ".cc"}

# 検証対象外のディレクトリ名（hookスクリプト等、直接実行できないファイル）
_SKIP_DIR_NAMES = {"hooks"}

# コード実行として認めるパターン（ホワイトリスト）
_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\b"),       # uv run (Python)
    re.compile(r"\bgo\s+run\b"),       # go run
    re.compile(r"\bcargo\s+run\b"),    # cargo run
    re.compile(r"\./[\w./-]+"),        # ./binary (C/C++ compiled)
]

# テストフレームワーク等の除外パターン
_EXCLUDE_PATTERNS = [
    re.compile(r"\buv\s+run\s+(pytest|py\.test)\b"),
    re.compile(r"\buv\s+run\s+.*-m\s+(pytest|unittest)\b"),
    re.compile(r"\bgo\s+test\b"),
    re.compile(r"\bcargo\s+(test|clippy|check|bench)\b"),
    # インライン実行（実質検証なし）
    re.compile(r"\buv\s+run\s+python3?\s+-c\b"),
    # no-op コマンド
    re.compile(r"\buv\s+run\s+(true|false|echo|cat|ls|pwd|:|which|type)\b"),
    # ./trivial
    re.compile(r"\./?(true|false|echo)\b"),
]

# テスト実行として認めるパターン（テストファイルに対してのみ有効）
_TEST_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\s+(pytest|py\.test)\b"),
    re.compile(r"\buv\s+run\s+.*-m\s+(pytest|unittest)\b"),
    re.compile(r"\bgo\s+test\b"),
    re.compile(r"\bcargo\s+test\b"),
]

_EXEC_TIMEOUT = 30


class ExecPlan(NamedTuple):
    steps: list[list[str]]
    tmp_file: str | None
    cwd: str | None


def is_code_execution(cmd: str) -> bool:
    """ホワイトリストに合致し、除外パターンに該当しないか判定."""
    if any(p.search(cmd) for p in _EXCLUDE_PATTERNS):
        return False
    return any(p.search(cmd) for p in _EXEC_PATTERNS)


def _normalize(cmd: str) -> str:
    """行継続（バックスラッシュ + 改行）を除去."""
    return cmd.replace("\\\n", " ")


def _looks_like_git_commit(command: str) -> bool:
    """git commit の直接・間接実行を検出."""
    cmd = _normalize(command)
    if re.search(r"\bgit\s+commit\b", cmd):
        return True
    # 変数展開: git $cmd, git ${VAR:-commit}
    if re.search(r"\bgit\s+\$", cmd):
        return True
    return False


def _cmd_references_file(cmd: str, file_path: str) -> bool:
    """コマンド文字列が指定ファイルを参照しているか判定."""
    if file_path in cmd:
        return True
    basename = file_path.rsplit("/", 1)[-1]
    if basename and basename in cmd:
        return True
    return False


def _is_test_file(file_path: str) -> bool:
    """テストファイルかどうかを判定."""
    basename = os.path.basename(file_path)
    return basename.startswith("test_") or basename.endswith("_test.py")


def _is_test_execution(cmd: str) -> bool:
    """テストフレームワーク経由の実行かどうかを判定."""
    return any(p.search(cmd) for p in _TEST_EXEC_PATTERNS)


def _build_exec_plan(file_path: str) -> ExecPlan:
    """拡張子・ファイル種別に応じた実行プランを構築."""
    ext = os.path.splitext(file_path)[1]

    if ext == ".py":
        if _is_test_file(file_path):
            return ExecPlan([["uv", "run", "pytest", file_path]], None, None)
        return ExecPlan([["uv", "run", "python3", file_path]], None, None)

    if ext == ".go":
        return ExecPlan([["go", "run", file_path]], None, None)

    if ext == ".rs":
        cwd = find_project_root(os.path.dirname(file_path), "Cargo.toml")
        return ExecPlan([["cargo", "run"]], None, cwd)

    if ext in (".c", ".cpp", ".cc"):
        suffix = ".exe" if sys.platform == "win32" else ""
        tmp = tempfile.mktemp(suffix=suffix)
        compiler = "gcc" if ext == ".c" else "g++"
        return ExecPlan([[compiler, file_path, "-o", tmp], [tmp]], tmp, None)

    return ExecPlan([], None, None)


def _execute_file(file_path: str) -> tuple[str, int, str]:
    """ファイルを実行して (file_path, exit_code, combined_output) を返す."""
    plan = _build_exec_plan(file_path)
    if not plan.steps:
        return file_path, 0, ""

    combined: list[str] = []
    exit_code = 0
    try:
        for step in plan.steps:
            try:
                result = subprocess.run(
                    step,
                    capture_output=True,
                    text=True,
                    timeout=_EXEC_TIMEOUT,
                    cwd=plan.cwd,
                )
            except subprocess.TimeoutExpired:
                combined.append(f"[timeout: {_EXEC_TIMEOUT}s]")
                return file_path, 1, "\n".join(combined)
            except FileNotFoundError as e:
                combined.append(f"[command not found: {e.filename}]")
                return file_path, 1, "\n".join(combined)

            if result.stdout.strip():
                combined.append(result.stdout.strip())
            if result.stderr.strip():
                combined.append(result.stderr.strip())
            if result.returncode != 0:
                exit_code = result.returncode
                break
    finally:
        if plan.tmp_file and os.path.exists(plan.tmp_file):
            os.unlink(plan.tmp_file)

    return file_path, exit_code, "\n".join(combined)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_path(transcript_path: str) -> str:
    return os.path.join(os.path.dirname(transcript_path), "verification-cache.json")


def _load_cache(transcript_path: str) -> dict:
    path = _cache_path(transcript_path)
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(
    transcript_path: str,
    cache: dict,
    results: list[tuple[str, int, str]],
    edited_files: dict[str, int],
) -> None:
    for fp, exit_code, output in results:
        cache[fp] = {
            "edit_seq": edited_files.get(fp, -1),
            "exit_code": exit_code,
            "output": output,
        }
    path = _cache_path(transcript_path)
    try:
        with open(path, "w") as f:
            json.dump(cache, f)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _block(reason: str) -> None:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)


def _format_results(results: list[tuple[str, int, str]]) -> str:
    parts: list[str] = []
    for fp, exit_code, output in sorted(results):
        status = "OK" if exit_code == 0 else f"FAILED (exit {exit_code})"
        header = f"  [{status}] {fp}"
        if output:
            indented = "\n".join(f"    {line}" for line in output.splitlines())
            parts.append(f"{header}\n{indented}")
        else:
            parts.append(f"{header}\n    (no output)")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not _looks_like_git_commit(command):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        _block("transcript_path が取得できないため、コード実行の検証ができません。")
        return

    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        _block("トランスクリプトが読み取れないため、コード実行の検証ができません。")
        return

    edited_files: dict[str, int] = {}  # {file_path: last_edit_seq}
    verified: set[str] = set()
    seq = 0

    for line in lines:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue

        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue

            name = block.get("name", "")
            inp = block.get("input", {})

            if name in ("Edit", "Write"):
                fp = inp.get("file_path", "") or inp.get("path", "")
                if fp and os.path.splitext(fp)[1] in _CODE_EXTENSIONS:
                    path_parts = set(fp.replace("\\", "/").split("/"))
                    if _SKIP_DIR_NAMES & path_parts:
                        continue
                    edited_files[fp] = seq
            elif name == "Bash":
                cmd = inp.get("command", "")
                if is_code_execution(cmd):
                    for fp, edit_seq in edited_files.items():
                        if edit_seq < seq and _cmd_references_file(cmd, fp):
                            verified.add(fp)
                elif _is_test_execution(cmd):
                    for fp, edit_seq in edited_files.items():
                        if edit_seq < seq and _is_test_file(fp) and _cmd_references_file(cmd, fp):
                            verified.add(fp)
            seq += 1

    unverified = set(edited_files) - verified
    if not unverified:
        return

    # キャッシュ確認: 前回実行済みでedit_seqが同じならスキップ
    cache = _load_cache(transcript_path)
    need_exec: set[str] = set()
    for fp in unverified:
        cached = cache.get(fp)
        if cached and cached.get("edit_seq") == edited_files[fp]:
            continue
        need_exec.add(fp)

    if not need_exec:
        return  # 全てキャッシュ済み → approve

    # 並列実行
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(_execute_file, fp) for fp in sorted(need_exec)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    _save_cache(transcript_path, cache, results, edited_files)

    listing = _format_results(results)
    _block(f"コード検証結果を確認してください:\n{listing}")


if __name__ == "__main__":
    main()
