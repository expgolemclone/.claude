#!/usr/bin/env python3
"""PreToolUse hook: block git commit if code hasn't been executed since last file edit."""

import json
import re
import sys

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
]


def is_code_execution(cmd: str) -> bool:
    """ホワイトリストに合致し、除外パターンに該当しないか判定."""
    if any(p.search(cmd) for p in _EXCLUDE_PATTERNS):
        return False
    return any(p.search(cmd) for p in _EXEC_PATTERNS)


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    # 引用符内の文字列を除去して誤検知を防ぐ
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)

    if not re.search(r"\bgit\s+commit\b", stripped):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        return

    last_edit_seq = -1
    last_run_seq = -1
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
                last_edit_seq = seq
            elif name == "Bash":
                cmd = inp.get("command", "")
                if is_code_execution(cmd):
                    last_run_seq = seq
            seq += 1

    if last_edit_seq >= 0 and last_run_seq <= last_edit_seq:
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "コミット前にコードを実行して動作確認を行ってください。\n"
                    "Edit/Write 後にコード実行（uv run/go run/cargo run/./binary）が確認できません。\n"
                    "pytest 等のテストフレームワークはコード実行に含まれません。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
