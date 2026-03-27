"""Shared utility: walk up directory tree to find a project root marker file."""

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
