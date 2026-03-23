"""Shared constants for NixOS configuration protection hooks."""

PROTECTED_PATTERNS = [
    r"sysusers\.enable",
    r"userborn\.enable",
    r"mutableUsers",
    r"initialPassword",
    r"hashedPassword",
    r"password\s*=",
]
