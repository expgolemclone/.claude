#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): inject rebuild instruction when nix-config files are edited."""

import json
import sys
from pathlib import Path


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")

    if file_path and Path(file_path).resolve().is_relative_to(Path.home() / "nix-config"):
        json.dump(
            {
                "decision": "block",
                "reason": "nix-config file was modified. Run: sudo nixos-rebuild switch --flake ~/nix-config#nixos",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
