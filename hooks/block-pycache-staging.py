#!/usr/bin/env python3
"""PreToolUse hook: block git add/commit that includes __pycache__ or .pyc files.

Layer 1 — prevents new staging of bytecode artifacts at git-add time and
provides a safety-net check at git-commit time.
"""

import json
import re
import subprocess
import sys


def _strip_quotes(command: str) -> str:
    """Remove quoted strings to avoid false positives from commit messages."""
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    return stripped


def _is_pycache_path(text: str) -> bool:
    """Return True if text contains __pycache__ or .pyc path references."""
    return bool(re.search(r"__pycache__|\.pyc\b", text))


def _is_bulk_add(stripped: str) -> bool:
    """Return True if the git add command uses bulk patterns like ., -A, --all."""
    # git add with no path args, or with . / -A / --all
    after_add = re.sub(r"^.*\bgit\s+add\b", "", stripped)
    # Remove flags like -f, --force, -v, etc. but keep -A and --all
    flags_only = re.sub(r"(?<!\w)-[fNnvq](?:\b|$)", "", after_add)
    flags_only = flags_only.strip()
    if not flags_only:
        return True
    if re.search(r"(?:^|\s)(\.|-A|--all)(?:\s|$)", flags_only):
        return True
    return False


def _has_untracked_pycache() -> bool:
    """Check if untracked __pycache__ files exist that would be staged."""
    result = subprocess.run(
        ["git", "ls-files", "-o", "--directory",
         "--", "*__pycache__*", "**/__pycache__/**"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _check_git_add(command: str, stripped: str) -> None:
    """Block git add that targets __pycache__ files."""
    if _is_pycache_path(stripped):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "__pycache__ / .pyc のステージングは禁止されています。\n"
                    ".gitignore に __pycache__/ を追加してください。"
                ),
            },
            sys.stdout,
        )
        return

    if _is_bulk_add(stripped) and _has_untracked_pycache():
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "一括 git add に対象内に __pycache__ が含まれています。\n"
                    ".gitignore に __pycache__/ を追加するか、\n"
                    "パスを明示的に指定してください。"
                ),
            },
            sys.stdout,
        )


def _check_git_commit() -> None:
    """Block git commit when staged files include __pycache__ (safety net)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return

    pycache_files = [
        f for f in result.stdout.splitlines()
        if "__pycache__" in f or f.endswith(".pyc")
    ]
    if pycache_files:
        file_list = "\n".join(f"  - {f}" for f in pycache_files[:5])
        json.dump(
            {
                "decision": "block",
                "reason": (
                    f"ステージングに __pycache__ / .pyc が含まれています:\n"
                    f"{file_list}\n\n"
                    "git reset HEAD -- <path> で解除してください。"
                ),
            },
            sys.stdout,
        )


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    stripped = _strip_quotes(command)

    if re.search(r"\bgit\s+add\b", stripped):
        _check_git_add(command, stripped)
    elif re.search(r"\bgit\s+commit\b", stripped):
        _check_git_commit()


if __name__ == "__main__":
    main()
