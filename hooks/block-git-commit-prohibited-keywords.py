#!/usr/bin/env python3
"""PreToolUse hook: block git commit/push when messages contain prohibited keywords."""

import json
import re
import subprocess
import sys

BLOCKED_KEYWORDS = [
    "authored", "claude", "anthropic",
    "ai", "llm", "gemini", "openai",
    "foundation", "copilot", "gpt", "chatgpt",
    "bard", "codeium", "cursor", "tabnine", "cody", "devin",
    "agent", "assistant", "エージェント",
]


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a word-boundary regex for a keyword."""
    return re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)


def extract_commit_portion(command: str) -> str:
    """Extract the portion of the command starting from ``git commit``."""
    match = re.search(r"\bgit\s+commit\b", command)
    if match:
        return command[match.start():]
    return ""


def find_tainted_commits() -> list[tuple[str, str, str]]:
    """Search git log for commits containing prohibited keywords.

    Returns list of (short_hash, subject, keyword) tuples.
    """
    combined = "|".join(re.escape(kw) for kw in BLOCKED_KEYWORDS)
    pattern = re.compile(rf"\b({combined})\b", re.IGNORECASE)

    proc = subprocess.run(
        ["git", "log", "--all", f"--grep=\\b({combined})\\b", "-i", "-P",
         "--format=%h %s"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    results: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for line in proc.stdout.strip().splitlines():
        parts = line.split(" ", 1)
        short_hash = parts[0]
        if short_hash in seen:
            continue
        seen.add(short_hash)
        subject = parts[1] if len(parts) > 1 else ""
        m = pattern.search(subject)
        keyword = m.group(1) if m else "?"
        results.append((short_hash, subject, keyword))
    return results


def check_commit(command: str) -> None:
    """Block git commit if the message contains a prohibited keyword."""
    commit_part = extract_commit_portion(command)
    if not commit_part:
        return

    for keyword in BLOCKED_KEYWORDS:
        if _keyword_pattern(keyword).search(commit_part):
            json.dump(
                {
                    "decision": "block",
                    "reason": f"commit メッセージに '{keyword}' を含めることは禁止されています。git add と git commit は別コマンドで実行してください。",
                },
                sys.stdout,
            )
            return


def check_push() -> None:
    """Block git push if any commit in the log contains a prohibited keyword."""
    tainted = find_tainted_commits()
    if not tainted:
        return

    lines = [f"  {h} {s} (keyword: {kw})" for h, s, kw in tainted]
    json.dump(
        {
            "decision": "block",
            "reason": (
                "git log に禁止キーワードを含むコミットが見つかりました:\n"
                + "\n".join(lines)
                + "\ngit rebase -i で該当コミットのメッセージを修正してください。"
            ),
        },
        sys.stdout,
    )


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if re.search(r"\bgit\s+push\b", command):
        check_push()
        return

    if re.search(r"\bgit\s+commit\b", command):
        check_commit(command)
        return


if __name__ == "__main__":
    main()
