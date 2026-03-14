#!/usr/bin/env python3
"""Stop hook: auto commit, push, and rebuild when nix-config was modified."""

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

    errors: list[str] = []

    # git add + commit
    run("git", "add", "-A")
    result = run("git", "commit", "-m", "nix: update config")
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        errors.append(f"git commit failed:\n{result.stderr}")

    # git push
    if not errors:
        result = run("git", "push")
        if result.returncode != 0:
            errors.append(f"git push failed:\n{result.stderr}")

    # nixos-rebuild
    if not errors:
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
