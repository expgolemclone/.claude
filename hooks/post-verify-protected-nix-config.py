#!/usr/bin/env python3
"""PostToolUse hook: verify protected lines in configuration.nix haven't changed."""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nix_protected import PROTECTED_PATTERNS

CONFIG_PATH = Path.home() / "nix-config" / "hosts" / "nixos" / "configuration.nix"
HASH_FILE = Path("/tmp/.nix-config-protected-hash")


def extract_protected_lines(content: str) -> list[str]:
    lines = []
    for line in content.splitlines():
        for pattern in PROTECTED_PATTERNS:
            if re.search(pattern, line):
                lines.append(line.strip())
                break
    return sorted(lines)


def compute_hash(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def main() -> None:
    if not CONFIG_PATH.exists():
        return

    current_lines = extract_protected_lines(CONFIG_PATH.read_text())
    if not current_lines:
        return

    current_hash = compute_hash(current_lines)

    if not HASH_FILE.exists():
        HASH_FILE.write_text(current_hash)
        return

    saved_hash = HASH_FILE.read_text().strip()
    if current_hash == saved_hash:
        return

    print(
        f"configuration.nix の保護対象行が変更されました。\n"
        f"変更を元に戻してください: git checkout hosts/nixos/configuration.nix\n"
        f"保護行: {current_lines}",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    # PostToolUse receives JSON on stdin but we don't need it
    sys.stdin.read()
    main()
