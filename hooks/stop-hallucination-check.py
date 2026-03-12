#!/usr/bin/env python3
"""Stop hook: warn when responding without primary source verification."""

import json
import sys

MIN_RESPONSE_LENGTH = 200


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    last_msg = data.get("last_assistant_message", "")
    if len(last_msg) < MIN_RESPONSE_LENGTH:
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    used_any_tool = False

    try:
        with open(transcript_path) as f:
            lines = f.readlines()

        # 最後のユーザーメッセージ行を探す
        # トランスクリプト形式: entry["type"] == "user" がユーザーメッセージ
        last_user_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            try:
                entry = json.loads(lines[i])
                if entry.get("type") == "user":
                    last_user_idx = i
                    break
            except json.JSONDecodeError:
                continue

        if last_user_idx < 0:
            return

        # ユーザーメッセージ以降のツール使用をチェック
        # ツール使用は entry["message"]["content"][] 内の
        # {"type": "tool_use", "name": "ToolName"} として記録される
        for line in lines[last_user_idx + 1 :]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = entry.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    used_any_tool = True
                    break
            if used_any_tool:
                break

    except (OSError, json.JSONDecodeError):
        return

    if used_any_tool:
        return

    json.dump(
        {
            "decision": "block",
            "reason": (
                "この回答には一次情報による検証が含まれていません。\n"
                "知識ベースの質問に回答している場合は、WebSearch または WebFetch で"
                "一次情報を確認してから回答してください。\n"
                "コーディングタスクへの応答であれば、そのまま終了して問題ありません。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
