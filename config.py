"""Path constants for the test infrastructure. Not imported by hooks."""

from pathlib import Path

# Project root: ~/.claude
PROJECT_ROOT = Path(__file__).resolve().parent

HOOKS_DIR = PROJECT_ROOT / "hooks"
TESTS_DIR = PROJECT_ROOT / "tests"
RULES_DIR = PROJECT_ROOT / "rules"
SETTINGS_JSON = PROJECT_ROOT / "settings.json"
