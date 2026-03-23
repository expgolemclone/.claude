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
            "defaultMode": "bypassPermissions",
            "deny": ["Agent"],
        },
        "skipDangerousModePermissionPrompt": True,
        "model": "claude-opus-4-6",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("inject-extension-rules-toml.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-json-direct-edit.py"),
                    py("block-protected-nix-config.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-add-force-staging.py"),
                    py("block-git-commit-prohibited-keywords.py"),
                    py("block-git-commit-protected-changes.py"),
                    py("block-nixos-rebuild-protected-changes.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("post-verify-protected-nix-config.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-non-python-hook-scripts.py"),
                ]},
            ],
            "Stop": [
                {"hooks": [
                    py("stop-require-git-commit-and-push.py", timeout=15),
                    py("stop-nixos-rebuild-on-config-change.py", timeout=300),
                    py("stop-require-source-verification.py", timeout=15),
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
                    py("inject-extension-rules-toml.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-json-direct-edit.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-add-force-staging.py"),
                    py("block-git-commit-prohibited-keywords.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [
                    py("block-non-python-hook-scripts.py"),
                ]},
            ],
            "Stop": [
                {"matcher": "", "hooks": [
                    py("stop-require-git-commit-and-push.py", timeout=15),
                    py("stop-require-source-verification.py", timeout=15),
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
