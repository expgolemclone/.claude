#!/usr/bin/env python3
"""Stop hook: detect __pycache__ / .pyc files already tracked by git.

Layer 2 — catches bytecode artifacts that slipped through Layer 1
(e.g. committed before the hook existed, or added outside Claude Code).
Also verifies .gitignore coverage.
"""

import json
import subprocess
import sys
from pathlib import Path


def _get_tracked_pycache(cwd: str) -> list[str]:
    """Return tracked file paths containing __pycache__ or ending in .pyc."""
    result = subprocess.run(
        ["git", "ls-files", "--", "*__pycache__*", "**/__pycache__/**", "*.pyc"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.splitlines() if f.strip()]


def _check_gitignore(cwd: str) -> bool:
    """Return True if .gitignore contains a __pycache__ rule."""
    gitignore = Path(cwd) / ".gitignore"
    if not gitignore.is_file():
        return False
    text = gitignore.read_text(encoding="utf-8", errors="replace")
    return any("__pycache__" in line for line in text.splitlines())


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    cwd = data.get("cwd", "")
    if not cwd:
        return

    tracked = _get_tracked_pycache(cwd)
    has_gitignore_rule = _check_gitignore(cwd)

    reasons: list[str] = []

    if tracked:
        file_list = "\n".join(f"  - {f}" for f in tracked[:10])
        reasons.append(
            f"git追跡されている __pycache__ / .pyc が {len(tracked)} 件あります:\n"
            f"{file_list}\n\n"
            "git rm --cached -r <path> で追跡を解除してください。"
        )

    if not has_gitignore_rule:
        reasons.append(
            ".gitignore に __pycache__/ エントリがありません。\n"
            "追加して今後の追跡を防止してください。"
        )

    if reasons:
        json.dump(
            {
                "decision": "block",
                "reason": "\n\n".join(reasons),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
