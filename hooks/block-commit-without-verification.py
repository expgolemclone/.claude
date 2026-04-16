#!/usr/bin/env python3
"""PreToolUse hook: block git commit until all edited code files are executed.

Scans the transcript for Edit/Write and Bash tool_use entries.
Edited code files must have a corresponding execution command in the
transcript before a commit is allowed.

Verification target: Directly executable files (with if __name__ == "__main__" block)
"""

import json
import os
import re
import sys

# Target extensions for executable code files
_CODE_EXTENSIONS = {".py", ".go", ".rs", ".c", ".cpp", ".cc"}

# Skip directory names (hook scripts, etc.)
_SKIP_DIR_NAMES = {"hooks"}

# Code execution patterns (whitelist)
_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\s+python3?\b"),
    re.compile(r"\bgo\s+run\b"),
    re.compile(r"\bgo\s+build\b"),
    re.compile(r"\bcargo\s+run\b"),
    re.compile(r"\./\w[\w./-]*"),
]

# Exclude patterns that match but are not actual executions
_EXCLUDE_PATTERNS = [
    re.compile(r"\buv\s+run\s+python3?\s+-c\b"),
    re.compile(r"\buv\s+run\s+python3?\s+-m\s+(pytest|unittest)\b"),
    re.compile(r"\./?(true|false|echo)\b"),
]

# Test execution patterns (only valid for test files)
_TEST_EXEC_PATTERNS = [
    re.compile(r"\buv\s+run\s+(pytest|py\.test)\b"),
    re.compile(r"\buv\s+run\s+.*-m\s+(pytest|unittest)\b"),
    re.compile(r"\bgo\s+test\b"),
    re.compile(r"\bcargo\s+test\b"),
]


def is_code_execution(cmd: str) -> bool:
    """Check if command matches whitelist and not exclude patterns."""
    if any(p.search(cmd) for p in _EXCLUDE_PATTERNS):
        return False
    return any(p.search(cmd) for p in _EXEC_PATTERNS)


def _has_main_block(file_path: str) -> bool:
    """Check if file contains 'if __name__ == "__main__"' block."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Detect various forms of if __name__ == "__main__"
        return bool(re.search(r"if\s+__name__\s*[=!]+\s*['\"]__main__['\"]", content))
    except (OSError, UnicodeDecodeError):
        return False


def _normalize(cmd: str) -> str:
    """Remove line continuation (backslash + newline)."""
    return cmd.replace("\\\n", " ")


def _looks_like_git_commit(command: str) -> bool:
    """Detect direct or indirect git commit execution."""
    cmd = _normalize(command)
    if re.search(r"\bgit\s+commit\b", cmd):
        return True
    if re.search(r"\bgit\s+\$", cmd):
        return True
    return False


def _cmd_references_file(cmd: str, file_path: str) -> bool:
    """Check if command references the specified file."""
    if file_path in cmd:
        return True
    basename = file_path.replace("\\", "/").rsplit("/", 1)[-1]
    if basename:
        # Fix: Allow path separators like / in matching
        pattern = rf"(?:^|\s|[\"'/])({re.escape(basename)})(?:\s|[\"'/]|$)"
        if re.search(pattern, cmd):
            return True
    # Go: ./... matches all .go files in project
    if file_path.endswith(".go") and "./..." in cmd:
        return True
    return False


def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    basename = os.path.basename(file_path)
    ext = os.path.splitext(basename)[1]
    # Python: test_*.py, *_test.py
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    # Go: *_test.go
    if basename.endswith("_test.go"):
        return True
    # C/C++: test_*.(c|cpp|cc)
    if basename.startswith("test_") and ext in (".c", ".cpp", ".cc"):
        return True
    return False


def _is_test_execution(cmd: str) -> bool:
    """Check if command is a test framework execution."""
    return any(p.search(cmd) for p in _TEST_EXEC_PATTERNS)


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not _looks_like_git_commit(command):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        json.dump(
            {"decision": "block", "reason": "transcript_path not available for verification"},
            sys.stdout,
        )
        return

    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        json.dump(
            {"decision": "block", "reason": "Cannot read transcript for verification"},
            sys.stdout,
        )
        return

    edited_files: dict[str, int] = {}
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
                    # Only verify files with if __name__ == "__main__" or test files
                    if _has_main_block(fp) or _is_test_file(fp):
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
                "テストファイルはテスト実行（例: uv run pytest <file>）で検証してください。\n"
                "上記のフルパスをそのまま指定できます。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
