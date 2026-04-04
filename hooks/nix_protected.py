"""Shared constants and utilities for NixOS configuration protection hooks."""

import re

PROTECTED_PATTERNS = [
    r"sysusers\.enable",
    r"userborn\.enable",
    r"mutableUsers",
    r"initialPassword",
    r"hashedPassword",
    r"password\s*=",
]


def check_config_diff(diff_text: str) -> str | None:
    """diff 中の configuration.nix 保護対象行の変更を検出."""
    in_config_file = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            in_config_file = "configuration.nix" in line
            continue
        if not in_config_file:
            continue
        if not (line.startswith("+") or line.startswith("-")):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        for pattern in PROTECTED_PATTERNS:
            if re.search(pattern, line):
                return f"configuration.nix の保護対象行が変更されています: {pattern}\n変更行: {line.strip()}"
    return None


def check_mkforce_override(diff_text: str) -> str | None:
    """diff 中の configuration.nix 内の mkForce による保護対象の上書きを検出."""
    in_config_file = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            in_config_file = "configuration.nix" in line
            continue
        if not in_config_file:
            continue
        if not line.startswith("+"):
            continue
        if line.startswith("+++"):
            continue
        if "mkForce" not in line:
            continue
        for pattern in PROTECTED_PATTERNS:
            if re.search(pattern, line):
                return f"mkForce で保護対象の設定を上書きしようとしています: {line.strip()}"
    return None
