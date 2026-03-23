"""Shared test helpers for hook subprocess tests."""

import json
import subprocess
import sys


def run_hook_process(hook_path: str, payload: dict) -> dict | None:
    """Run a hook script as a subprocess, sending JSON via stdin."""
    result = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None
