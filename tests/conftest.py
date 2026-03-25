"""Shared test helpers and path constants for hook subprocess tests."""

import json
import subprocess
import sys
from pathlib import Path

# Project root: ~/.claude
PROJECT_ROOT = Path(__file__).resolve().parent.parent

HOOKS_DIR = PROJECT_ROOT / "hooks"
TESTS_DIR = PROJECT_ROOT / "tests"
RULES_DIR = PROJECT_ROOT / "rules"
SETTINGS_JSON = PROJECT_ROOT / "settings.json"


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
