#!/usr/bin/env python3
"""Stop hook: rebuild NixOS when nix-config was modified."""

import json
import subprocess
import sys
from pathlib import Path

FLAG = Path("/tmp/.nix-config-dirty")
NIX_CONFIG = Path.home() / "nix-config"


def run(*args: str, cwd: Path = NIX_CONFIG) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd)


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active") or data.get("permission_mode") == "plan":
        return

    if not FLAG.exists():
        return

    # tree が dirty なら rebuild しない（stop-git-check.py に任せる）
    result = run("git", "status", "--porcelain")
    if result.stdout.strip():
        return

    errors: list[str] = []

    result = run("sudo", "nixos-rebuild", "switch", "--flake", f"{NIX_CONFIG}#nixos")
    if result.returncode != 0:
        errors.append(f"nixos-rebuild failed:\n{result.stderr}")

    if errors:
        json.dump(
            {"decision": "block", "reason": "\n".join(errors)},
            sys.stdout,
        )
    else:
        FLAG.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
