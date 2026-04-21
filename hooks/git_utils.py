"""Shared git helpers for stop-scan hooks."""

import subprocess
from pathlib import Path


def git_tracked_files(root: Path, patterns: list[str] | None = None) -> set[Path]:
    """Return paths listed by ``git ls-files`` under *root*.

    *patterns* are optional glob-style arguments forwarded after ``--``
    (e.g. ``["*.py"]``).  Returns an empty set on any git failure.
    """
    cmd = ["git", "ls-files"]
    if patterns:
        cmd += ["--"] + patterns
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=root,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {root / line for line in result.stdout.splitlines() if line}


def git_tracked_py_files(root: Path) -> set[Path]:
    """Shortcut: tracked ``*.py`` files under *root*."""
    return git_tracked_files(root, ["*.py"])
