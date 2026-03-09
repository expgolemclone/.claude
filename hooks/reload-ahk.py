#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): reload AutoHotkey after .ahk file edits."""

import json
import os
import subprocess
import sys

AHK_DIR = r"C:\Users\0000250059\Documents\AutoHotkey"
AHK_EXE = os.path.join(AHK_DIR, ".tools", "AutoHotkey-v2", "AutoHotkey64.exe")


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
        files = [f for f in os.listdir(AHK_DIR) if f.endswith("-launcher.ahk")]
    except OSError:
        return

    for f in files:
        script = os.path.join(AHK_DIR, f)
        try:
            subprocess.Popen(
                [AHK_EXE, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
