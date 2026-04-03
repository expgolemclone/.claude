#!/usr/bin/env python3
"""PreToolUse hook (Bash): block package installs that bypass lockfiles."""

import json
import re
import sys

_CMD_BOUNDARY = r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)"
_SUDO = r"(?:sudo\s+)?"

# pip / uv pip install without -r/--requirement
_PIP_INSTALL_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"(?:uv\s+)?pip3?\s+install\b"
)
_PIP_REQ_FLAG_RE = re.compile(r"\s+(?:-r|--requirement)\b")

# npm install with --no-package-lock, or with explicit package args
_NPM_INSTALL_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"npm\s+install\b"
)
_NPM_NO_LOCK_RE = re.compile(r"--no-package-lock")

# yarn add (always modifies deps directly)
_YARN_ADD_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"yarn\s+add\b"
)

# cargo install (direct binary install, not via Cargo.lock)
_CARGO_INSTALL_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"cargo\s+install\b"
)

# uv sync / uv pip sync — always allowed
_UV_SYNC_RE = re.compile(
    _CMD_BOUNDARY + r"uv\s+(?:pip\s+)?sync\b"
)

# npm ci — lockfile-based, always allowed
_NPM_CI_RE = re.compile(
    _CMD_BOUNDARY + _SUDO + r"npm\s+ci\b"
)


def _strip_quotes(command: str) -> str:
    result = re.sub(r'"[^"]*"', '""', command)
    return re.sub(r"'[^']*'", "''", result)


def _has_package_args(command: str, install_keyword: str) -> bool:
    """Check if command has package name arguments after install keyword."""
    idx = command.find(install_keyword)
    if idx < 0:
        return False
    after = command[idx + len(install_keyword):]
    tokens = after.split()
    for token in tokens:
        if token.startswith("-"):
            continue
        if token in ("&&", "||", ";", "|"):
            break
        return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    command: str = data.get("tool_input", {}).get("command", "")
    if not command:
        return

    stripped = _strip_quotes(command)

    if _UV_SYNC_RE.search(stripped) or _NPM_CI_RE.search(stripped):
        return

    if _PIP_INSTALL_RE.search(stripped):
        if not _PIP_REQ_FLAG_RE.search(stripped):
            json.dump(
                {
                    "decision": "block",
                    "reason": (
                        "lockfileを経由しないパッケージインストールは禁止です"
                        "（config: install_without_lock = false）。\n"
                        "uv pip install -r requirements.txt または uv sync を使用してください。"
                    ),
                },
                sys.stdout,
            )
            return

    if _YARN_ADD_RE.search(stripped):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "lockfileを経由しないパッケージインストールは禁止です"
                    "（config: install_without_lock = false）。\n"
                    "npm ci または yarn install --frozen-lockfile を使用してください。"
                ),
            },
            sys.stdout,
        )
        return

    if _NPM_INSTALL_RE.search(stripped) and _NPM_NO_LOCK_RE.search(stripped):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "--no-package-lock 付きのインストールは禁止です"
                    "（config: install_without_lock = false）。\n"
                    "npm ci を使用してください。"
                ),
            },
            sys.stdout,
        )
        return

    if _CARGO_INSTALL_RE.search(stripped):
        json.dump(
            {
                "decision": "block",
                "reason": (
                    "cargo install は lockfile を経由しません"
                    "（config: install_without_lock = false）。\n"
                    "Cargo.toml に依存を追加し cargo build を使用してください。"
                ),
            },
            sys.stdout,
        )
        return


if __name__ == "__main__":
    main()
