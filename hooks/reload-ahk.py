#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): reload AutoHotkey after .ahk file edits."""

import json
import subprocess
import sys
from pathlib import Path

AHK_DIR = Path.home() / "Documents" / "AutoHotkey"
AHK_EXE = AHK_DIR / ".tools" / "AutoHotkey-v2" / "AutoHotkey64.exe"


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path", "")

    if not file_path.endswith(".ahk"):
        return

    # Kill all AHK processes
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "AutoHotkey64.exe"],
            capture_output=True,
        )
    except FileNotFoundError:
        pass

    # Restart all launcher scripts
    try:
        launchers = [f for f in AHK_DIR.iterdir() if f.name.endswith("-launcher.ahk")]
    except OSError:
        return

    for script in launchers:
        try:
            subprocess.Popen(
                [str(AHK_EXE), str(script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
