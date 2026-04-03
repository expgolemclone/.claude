#!/usr/bin/env python3
"""Stop hook: rebuild NixOS when nix-config HEAD has changed since last rebuild."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HASH_FILE = Path(tempfile.gettempdir()) / ".nix-config-last-rebuild-hash"
NIX_CONFIG = Path.home() / "nix-config"


def run(*args: str, cwd: Path = NIX_CONFIG) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd)


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("permission_mode") == "plan":
        return

    # tree が dirty なら rebuild しない（stop-git-check.py に任せる）
    result = run("git", "status", "--porcelain")
    if result.stdout.strip():
        return

    # 現在の HEAD ハッシュを取得
    result = run("git", "rev-parse", "HEAD")
    if result.returncode != 0:
        return
    current_hash = result.stdout.strip()

    # 前回リビルド時のハッシュと比較
    last_hash = HASH_FILE.read_text().strip() if HASH_FILE.exists() else ""
    if current_hash == last_hash:
        return

    result = run("sudo", "nixos-rebuild", "switch", "--flake", f"{NIX_CONFIG}#nixos")
    if result.returncode != 0:
        json.dump(
            {"decision": "block", "reason": f"nixos-rebuild failed:\n{result.stderr}"},
            sys.stdout,
        )
    else:
        HASH_FILE.write_text(current_hash)


if __name__ == "__main__":
    main()
