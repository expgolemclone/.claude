#!/usr/bin/env python3
"""PreToolUse hook: block git commit when staged diff contains protected config changes."""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nix_protected import check_config_diff, check_mkforce_override

NIX_CONFIG = Path.home() / "nix-config"


def get_staged_diff(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True, text=True, cwd=cwd,
    )
    return result.stdout if result.returncode == 0 else ""


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\bgit\s+commit\b", command):
        return

    diff_text = get_staged_diff(NIX_CONFIG)
    if not diff_text.strip():
        return

    reason = check_config_diff(diff_text)
    if not reason:
        reason = check_mkforce_override(diff_text)

    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
