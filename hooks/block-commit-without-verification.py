#!/usr/bin/env python3
"""PreToolUse hook: block git commit if code hasn't been executed since last file edit."""

import json
import os
import re
import sys

# 検証対象とする拡張子（実行可能なコードファイルのみ）
_CODE_EXTENSIONS = {".py", ".go", ".rs", ".c", ".cpp", ".cc"}

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


def _block(reason: str) -> None:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)


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
                    edited_files[fp] = seq
            elif name == "Bash":
                cmd = inp.get("command", "")
                if is_code_execution(cmd):
                    for fp, edit_seq in edited_files.items():
                        if edit_seq < seq and _cmd_references_file(cmd, fp):
                            verified.add(fp)
            seq += 1

    unverified = set(edited_files) - verified
    if unverified:
        listing = "\n".join(f"  - {f}" for f in sorted(unverified))
        _block(
            "コミット前に編集したコードをそれぞれ実行して動作確認を行ってください。\n"
            f"以下のファイルの実行が確認できません:\n{listing}\n"
            "コード実行コマンドにファイルパスまたはファイル名を含めてください。"
        )


if __name__ == "__main__":
    main()
