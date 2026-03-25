#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): detect hotstring prefix conflicts in .ahk files."""

import json
import os
import re
import sys
from pathlib import Path

AHK_PROJECT_DIR = Path("C:/Users/0000250059/Documents/AutoHotkey")
EXCLUDE_DIRS = {".tools", ".git", ".log"}
HOTSTRING_RE = re.compile(r"^:([^:]*):(.+?)::", re.MULTILINE)


def find_ahk_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*.ahk"):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(root).parts):
            continue
        files.append(p)
    return files


def extract_hotstrings(file_path: Path) -> list[tuple[str, str, int]]:
    """Return list of (trigger, file_path_str, line_number)."""
    results = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return results
    for i, line in enumerate(content.splitlines(), 1):
        m = HOTSTRING_RE.match(line.strip())
        if m:
            results.append((m.group(2), str(file_path), i))
    return results


def find_prefix_conflicts(
    hotstrings: list[tuple[str, str, int]],
) -> list[tuple[tuple[str, str, int], tuple[str, str, int]]]:
    """Find pairs where one trigger is a proper prefix of another."""
    conflicts = []
    for i, (ta, fa, la) in enumerate(hotstrings):
        for j, (tb, fb, lb) in enumerate(hotstrings):
            if i >= j:
                continue
            if ta != tb and tb.startswith(ta):
                conflicts.append(((ta, fa, la), (tb, fb, lb)))
            elif ta != tb and ta.startswith(tb):
                conflicts.append(((tb, fb, lb), (ta, fa, la)))
    return conflicts


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not file_path.endswith(".ahk"):
        return

    try:
        Path(file_path).relative_to(AHK_PROJECT_DIR)
    except ValueError:
        return

    all_hotstrings = []
    for f in find_ahk_files(AHK_PROJECT_DIR):
        all_hotstrings.extend(extract_hotstrings(f))

    conflicts = find_prefix_conflicts(all_hotstrings)
    if not conflicts:
        return

    lines = []
    for (short_t, short_f, short_l), (long_t, long_f, long_l) in conflicts:
        sr = os.path.relpath(short_f, AHK_PROJECT_DIR)
        lr = os.path.relpath(long_f, AHK_PROJECT_DIR)
        lines.append(
            f"  '{short_t}' ({sr}:{short_l}) は '{long_t}' ({lr}:{long_l}) のプレフィックスです"
        )

    json.dump(
        {
            "decision": "block",
            "reason": "ホットストリングのプレフィックス競合が検出されました:\n"
            + "\n".join(lines),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
