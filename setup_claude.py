#!/usr/bin/env python3
"""Generate settings.json for Claude Code (native Claude Opus).

setup.py の構成を流用し、モデル設定のみ上書きする。
"""

import json
import platform
import sys
from pathlib import Path

from setup import build_linux_config, build_windows_config

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "settings.json"

CLAUDE_COMMON: dict[str, object] = {
    "model": "claude-opus-4-7",
    "effortLevel": "xhigh",
    "skipDangerousModePermissionPrompt": True,
}


def main() -> None:
    system = platform.system()
    if system == "Linux":
        config = build_linux_config(common=CLAUDE_COMMON)
    elif system == "Windows":
        config = build_windows_config(common=CLAUDE_COMMON)
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        sys.exit(1)

    TARGET.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Generated: {TARGET}")


if __name__ == "__main__":
    main()
