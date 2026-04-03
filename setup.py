#!/usr/bin/env python3
"""Generate OS-specific settings.json for Claude Code."""

import json
import platform
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "settings.json"


def hook(command, timeout=None):
    h = {"type": "command", "command": command}
    if timeout is not None:
        h["timeout"] = timeout
    return h


def build_common_config():
    return {
        "skipDangerousModePermissionPrompt": True,
    }


def build_linux_config():
    h = str(Path.home() / ".claude")

    def py(script, *args, timeout=None):
        cmd = f"python3 {h}/hooks/{script}"
        if args:
            cmd += " " + " ".join(args)
        return hook(cmd, timeout)

    return {
        **build_common_config(),
        "permissions": {
            "defaultMode": "bypassPermissions",
            "deny": ["Agent"],
        },
        "language": "ja",
        "voiceEnabled": True,
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("inject-extension-rules-toml.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-json-direct-edit.py"),
                    py("block-protected-nix-config.py"),
                    py("block-non-python-hook-scripts.py"),
                    py("block-any-type.py"),
                ]},
                {"matcher": "Write|Bash", "hooks": [
                    py("block-platform-specific-scripts.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-add-force-staging.py"),
                    py("block-git-commit-prohibited-keywords.py"),
                    py("block-commit-without-verification.py", timeout=120),
                    py("block-git-commit-protected-changes.py"),
                    py("block-nixos-rebuild-protected-changes.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("post-verify-protected-nix-config.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("post-cargo-clippy-on-rs-edit.py", timeout=120),
                    py("warn-hardcoded-paths.py"),
                ]},
            ],
            "Stop": [
                {"hooks": [
                    py("stop-lint-edited-python.py", timeout=300),
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
        **build_common_config(),
        "permissions": {
            "deny": ["Agent"],
            "defaultMode": "bypassPermissions",
        },
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("inject-extension-rules-toml.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("block-settings-json-direct-edit.py"),
                    py("block-non-python-hook-scripts.py"),
                    py("block-any-type.py"),
                ]},
                {"matcher": "Write|Bash", "hooks": [
                    py("block-platform-specific-scripts.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-add-force-staging.py"),
                    py("block-git-commit-prohibited-keywords.py"),
                    py("block-commit-without-verification.py", timeout=120),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [
                    py("post-cargo-clippy-on-rs-edit.py", timeout=120),
                    py("check-hotstring-conflicts.py"),
                    py("warn-hardcoded-paths.py"),
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

    TARGET.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Generated: {TARGET}")


if __name__ == "__main__":
    main()
