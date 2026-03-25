#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): run cargo clippy on .rs file changes and inject diagnostics."""

import json
import os
import subprocess
import sys


def find_cargo_root(start: str) -> str | None:
    """Walk up from start to find directory containing Cargo.toml."""
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "Cargo.toml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not file_path.endswith(".rs"):
        return

    project_root = find_cargo_root(os.path.dirname(file_path))
    if not project_root:
        return

    try:
        result = subprocess.run(
            ["cargo", "clippy", "--color=never", "--quiet"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return

    diagnostics = result.stderr.strip()
    if not diagnostics:
        return

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"cargo clippy diagnostics:\n{diagnostics}\nFix these issues.",
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
