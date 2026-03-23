#!/usr/bin/env python3
"""PreToolUse hook: block nixos-rebuild when protected config lines are changed."""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nix_protected import PROTECTED_PATTERNS

NIX_CONFIG = Path.home() / "nix-config"


def get_diff(cwd: Path) -> str:
    parts = []
    for extra_args in [[], ["--cached"]]:
        result = subprocess.run(
            ["git", "diff", *extra_args],
            capture_output=True, text=True, cwd=cwd,
        )
        if result.returncode == 0:
            parts.append(result.stdout)
    return "\n".join(parts)


def check_config_diff(diff_text: str) -> str | None:
    in_config_file = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            in_config_file = "configuration.nix" in line
            continue
        if not in_config_file:
            continue
        if not (line.startswith("+") or line.startswith("-")):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        for pattern in PROTECTED_PATTERNS:
            if re.search(pattern, line):
                return f"configuration.nix の保護対象行が変更されています: {pattern}\n変更行: {line.strip()}"
    return None


def check_mkforce_override(diff_text: str) -> str | None:
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        if line.startswith("+++"):
            continue
        if "mkForce" not in line:
            continue
        for pattern in PROTECTED_PATTERNS:
            if re.search(pattern, line):
                return f"mkForce で保護対象の設定を上書きしようとしています: {line.strip()}"
    return None


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not re.search(r"\bnixos-rebuild\b", command):
        return

    diff_text = get_diff(NIX_CONFIG)
    if not diff_text.strip():
        return

    reason = check_config_diff(diff_text)
    if not reason:
        reason = check_mkforce_override(diff_text)

    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
