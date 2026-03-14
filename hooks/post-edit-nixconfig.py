#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): set dirty flag when nix-config files are edited."""

import json
import sys
from pathlib import Path

FLAG = Path("/tmp/.nix-config-dirty")


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")

    if file_path and Path(file_path).resolve().is_relative_to(Path.home() / "nix-config"):
        FLAG.touch()


if __name__ == "__main__":
    main()
