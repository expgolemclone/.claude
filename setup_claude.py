#!/usr/bin/env python3
"""Generate OS-specific settings.json for Claude Code (Claude Opus, effort=max)."""

import json
import platform
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "settings.json"


def hook(command: str, timeout: int | None = None) -> dict[str, object]:
    h: dict[str, object] = {"type": "command", "command": command}
    if timeout is not None:
        h["timeout"] = timeout
    return h


def build_common_config() -> dict[str, object]:
    return {
        "model": "claude-opus-4-6",
        "skipDangerousModePermissionPrompt": True,
    }


def build_linux_config() -> dict[str, object]:
    h: str = str(Path.home() / ".claude")
    projects: str = str(Path.home() / "projects")

    def py(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        cmd: str = f"python3 {h}/hooks/{script}"
        if args:
            cmd += " " + " ".join(args)
        return hook(cmd, timeout)

    def project_py(project: str, script: str, *, timeout: int | None = None) -> dict[str, object]:
        cmd: str = f"python3 {projects}/{project}/hooks/{script}"
        return hook(cmd, timeout)

    return {
        **build_common_config(),
        "effortLevel": "max",
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
                    py("block-setup-py-cfg.py"),
                    py("block-manual-requirements-txt.py"),
                    py("block-wildcard-versions.py"),
                    py("block-missing-annotations.py"),
                    py("block-unbounded-dependency.py"),
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
                    py("block-prohibited-python-toolchains.py"),
                    py("block-install-without-lock.py"),
                    py("block-pycache-staging.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write|Bash", "hooks": [
                    py("post-verify-protected-nix-config.py"),
                ]},
                {"matcher": "Edit|Write", "hooks": [
                    py("post-cargo-clippy-on-rs-edit.py", timeout=120),
                    py("warn-hardcoded-paths.py"),
                    py("warn-structural-duplicates.py"),
                    py("block-magic-numbers.py"),
                    py("check-hotstring-conflicts.py"),
                    py("block-worker-in-tracked-datasource.py"),
                    py("block-scrape-interval.py"),
                    py("post-scan-fallbacks.py"),
                ]},
            ],
            "Stop": [
                {"hooks": [
                    py("stop-lint-edited-python.py", timeout=300),
                    py("stop-require-git-commit-and-push.py", timeout=15),
                    py("stop-nixos-rebuild-on-config-change.py", timeout=300),
                    py("stop-require-source-verification.py", timeout=15),
                    py("stop-scan-error-handling.py", timeout=15),
                    py("stop-scan-any-type.py", timeout=15),
                    py("stop-scan-pycache-tracked.py", timeout=15),
                    py("stop-warn-chrome-tabs.py", timeout=15),
                ]},
            ],
        },
    }


def build_windows_config() -> dict[str, object]:
    claude_home: str = (Path.home() / ".claude").as_posix()
    claude_home_bs: str = str(Path.home() / ".claude")

    def py(script: str, *args: str, timeout: int | None = None) -> dict[str, object]:
        cmd: str = f'python3 "{claude_home}/hooks/{script}"'
        if args:
            cmd += " " + " ".join(args)
        return hook(cmd, timeout)

    return {
        **build_common_config(),
        "effortLevel": "max",
        "permissions": {
            "deny": ["Task", "Agent"],
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
                    py("block-setup-py-cfg.py"),
                    py("block-manual-requirements-txt.py"),
                    py("block-wildcard-versions.py"),
                    py("block-missing-annotations.py"),
                    py("block-unbounded-dependency.py"),
                ]},
                {"matcher": "Write|Bash", "hooks": [
                    py("block-platform-specific-scripts.py"),
                ]},
                {"matcher": "Bash", "hooks": [
                    py("block-git-add-force-staging.py"),
                    py("block-git-commit-prohibited-keywords.py"),
                    py("block-commit-without-verification.py", timeout=120),
                    py("block-prohibited-python-toolchains.py"),
                    py("block-install-without-lock.py"),
                    py("block-pycache-staging.py"),
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [
                    py("post-cargo-clippy-on-rs-edit.py", timeout=120),
                    py("check-hotstring-conflicts.py"),
                    py("warn-hardcoded-paths.py"),
                    py("warn-structural-duplicates.py"),
                    py("block-magic-numbers.py"),
                    py("block-worker-in-tracked-datasource.py"),
                    py("block-scrape-interval.py"),
                    py("post-scan-fallbacks.py"),
                ]},
            ],
            "Stop": [
                {"matcher": "", "hooks": [
                    py("stop-require-git-commit-and-push.py", timeout=15),
                    py("stop-require-source-verification.py", timeout=15),
                    py("stop-scan-error-handling.py", timeout=15),
                    py("stop-scan-any-type.py", timeout=15),
                    py("stop-scan-pycache-tracked.py", timeout=15),
                    hook(
                        f'pwsh -NoProfile -ExecutionPolicy Bypass'
                        f' -File "{claude_home_bs}\\scripts\\notify-complete.ps1"'
                    ),
                ]},
            ],
        },
    }
def main() -> None:
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
