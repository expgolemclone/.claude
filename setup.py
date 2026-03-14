#!/usr/bin/env python3
"""Generate OS-specific settings.json for Claude Code."""

import json
import platform
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "settings.json"


def hook(command, timeout=None):
    h = {"type": "command", "command": command}
    if timeout is not None:
        h["timeout"] = timeout
    return h


def build_linux_config():
    h = str(Path.home() / ".claude")

    def py(script, *args, timeout=None):
        cmd = f"python3 {h}/hooks/{script}"
        if args:
            cmd += " " + " ".join(args)
        return hook(cmd, timeout)

    return {
        "permissions": {
            "defaultMode": "plan",
            "deny": ["Agent"],
        },
        "skipDangerousModePermissionPrompt": True,
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("inject-rules.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-direct-edit.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-force-add.py"),
                    py("block-git-commit-keywords.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [
                    py("post-edit-nixconfig.py", timeout=5),
                    py("enforce-python-hooks.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("post-bash-nixrebuild.py", timeout=5),
                ]},
            ],
            "Stop": [
                {"hooks": [
                    py("stop-git-check.py", timeout=15),
                    py("stop-git-issues.py", timeout=15),
                    py("stop-hallucination-check.py", timeout=15),
                ]},
            ],
        },
    }


def build_windows_config():
    claude_home = (Path.home() / ".claude").as_posix()
    claude_home_bs = str(Path.home() / ".claude")

    def py(script, *args, timeout=None):
        cmd = f'python3 "{claude_home}/hooks/{script}"'
        if args:
            cmd += " " + " ".join(args)
        return hook(cmd, timeout)

    return {
        "permissions": {
            "deny": ["Task", "Agent"],
            "defaultMode": "bypassPermissions",
        },
        "skipDangerousModePermissionPrompt": True,
        "effortLevel": "high",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("inject-rules.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-direct-edit.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("wsl-proxy.py", "pre"),
                    py("block-git-force-add.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [
                    py("reload-ahk.py"),
                    py("check-hotstring-conflicts.py"),
                    py("enforce-python-hooks.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("wsl-proxy.py", "post"),
                ]},
            ],
            "Stop": [
                {"matcher": "", "hooks": [
                    py("stop-git-check.py", timeout=15),
                    py("stop-git-issues.py", timeout=15),
                    hook(
                        f'pwsh -NoProfile -ExecutionPolicy Bypass'
                        f' -File "{claude_home_bs}\\scripts\\notify-complete.ps1"'
                    ),
                ]},
            ],
        },
    }


def main():
    system = platform.system()
    if system == "Linux":
        config = build_linux_config()
    elif system == "Windows":
        config = build_windows_config()
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        sys.exit(1)

    if TARGET.exists():
        backup = TARGET.with_suffix(".json.bak")
        shutil.copy2(TARGET, backup)
        print(f"Backed up: {TARGET} -> {backup}")

    TARGET.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Generated: {TARGET}")


if __name__ == "__main__":
    main()
