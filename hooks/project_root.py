"""Shared utilities to resolve project roots from a starting path."""

import os


def find_project_root(start: str, marker: str = "Cargo.toml") -> str | None:
    """Walk up from *start* to find directory containing *marker*."""
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, marker)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def find_git_root(start: str) -> str | None:
    """Walk up from *start* to find directory containing a .git entry."""
    d = os.path.abspath(start)
    while True:
        git_entry = os.path.join(d, ".git")
        if os.path.isdir(git_entry) or os.path.isfile(git_entry):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
