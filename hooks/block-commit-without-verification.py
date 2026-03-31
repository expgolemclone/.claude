#!/usr/bin/env python3
"""PreToolUse hook: block git commit until all edited code files are executed.

Scans the transcript for Edit/Write and Bash tool_use entries.
Edited code files must have a corresponding execution command in the
transcript before a commit is allowed.
"""

import json
import os
import re
import sys

# 検証対象とする拡張子（実行可能なコードファイルのみ）
_CODE_EXTENSIONS = {".py", ".go", ".rs", ".c", ".cpp", ".cc"}

# 検証対象外のディレクトリ名（hookスクリプト等、直接実行できないファイル）
_SKIP_DIR_NAMES = {"hooks"}

# コード実行として認めるパターン（ホワイトリスト）
_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\s+python3?\b"),  # uv run python / uv run python3
    re.compile(r"\bgo\s+run\b"),              # go run
    re.compile(r"\bgo\s+build\b"),            # go build
    re.compile(r"\bcargo\s+run\b"),           # cargo run
    re.compile(r"\./\w[\w./-]*"),              # ./binary (C/C++ compiled)
]

# 上記にマッチしても実行とみなさない除外パターン
_EXCLUDE_PATTERNS = [
    re.compile(r"\buv\s+run\s+python3?\s+-c\b"),                      # インライン実行
    re.compile(r"\buv\s+run\s+python3?\s+-m\s+(pytest|unittest)\b"),  # テストフレームワーク
    re.compile(r"\./?(true|false|echo)\b"),                            # trivial
]

# テスト実行として認めるパターン（テストファイルに対してのみ有効）
_TEST_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\s+(pytest|py\.test)\b"),
    re.compile(r"\buv\s+run\s+.*-m\s+(pytest|unittest)\b"),
    re.compile(r"\bgo\s+test\b"),
    re.compile(r"\bcargo\s+test\b"),
]


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
    basename = file_path.replace("\\", "/").rsplit("/", 1)[-1]
    if basename and re.search(rf"(?:^|\s|[\"']){re.escape(basename)}(?:\s|[\"']|$)", cmd):
        return True
    # Go: ./... はプロジェクト全パッケージを対象とするため、全 .go ファイルに一致
    if file_path.endswith(".go") and "./..." in cmd:
        return True
    return False


def _is_test_file(file_path: str) -> bool:
    """テストファイルかどうかを判定."""
    basename = os.path.basename(file_path)
    return basename.startswith("test_") or basename.endswith("_test.py")


def _is_test_execution(cmd: str) -> bool:
    """テストフレームワーク経由の実行かどうかを判定."""
    return any(p.search(cmd) for p in _TEST_EXEC_PATTERNS)


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not _looks_like_git_commit(command):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        json.dump(
            {"decision": "block", "reason": "transcript_path が取得できないため、コード実行の検証ができません。"},
            sys.stdout,
        )
        return

    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        json.dump(
            {"decision": "block", "reason": "トランスクリプトが読み取れないため、コード実行の検証ができません。"},
            sys.stdout,
        )
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

    unverified = sorted(set(edited_files) - verified)
    if not unverified:
        return

    listing = "\n".join(f"  - {fp}" for fp in unverified)
    json.dump(
        {
            "decision": "block",
            "reason": (
                "以下のファイルがまだ実行されていません。コミット前に実行してください:\n"
                f"{listing}\n\n"
                "ソースファイルは直接実行（例: uv run python <file>）、"
                "テストファイルはテスト実行（例: uv run pytest <file>）で検証してください。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
