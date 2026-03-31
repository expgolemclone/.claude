#!/usr/bin/env python3
"""Stop hook: run mypy, ruff, pylint on edited .py files."""

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
HOOKS_DIR = PROJECT_ROOT / "hooks"
CACHE_FILE = PROJECT_ROOT / ".cache" / "lint-hashes.json"


def load_toml(filename: str) -> dict:
    """Load a TOML file from config/."""
    path = CONFIG_DIR / filename
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except OSError:
        return {}


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def all_py_files() -> list[Path]:
    """Collect all .py files under hooks/."""
    return sorted(p for p in HOOKS_DIR.rglob("*.py") if p.is_file())


def load_cache() -> dict[str, str]:
    """Load cached hashes from .cache/lint-hashes.json."""
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(hashes: dict[str, str]) -> None:
    """Save hashes to .cache/lint-hashes.json."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)


def changed_files(cached: dict[str, str]) -> tuple[list[Path], dict[str, str]]:
    """Return files whose hash differs from cache, plus full current hashes."""
    current: dict[str, str] = {}
    changed: list[Path] = []
    for p in all_py_files():
        key = str(p)
        digest = file_sha256(p)
        current[key] = digest
        if cached.get(key) != digest:
            changed.append(p)
    return changed, current


def build_commands(
    files: list[Path],
    cli_cfg: dict,
) -> list[tuple[str, list[str]]]:
    """Build linter command lists from cli_defaults.toml config.

    Tools with ``module`` run via ``python3 -W <flag> -m <module>``.
    Tools with ``command`` run as a direct binary (e.g. ruff on NixOS).
    """
    linters = cli_cfg.get("python_linters", {})
    runner = linters.get("runner", ["uv", "run"])
    warn_flag = linters.get("python_warning_flag", "error")
    tools = linters.get("tools", {})

    file_strs = [str(f) for f in files]
    commands: list[tuple[str, list[str]]] = []

    for name in ("mypy", "ruff", "pylint"):
        tool_cfg = tools.get(name, {})
        extra_args = tool_cfg.get("args", [])
        command = tool_cfg.get("command")

        if command:
            cmd = [*command, *extra_args, *file_strs]
        else:
            module = tool_cfg.get("module", name)
            cmd = [*runner, "python3", "-W", warn_flag, "-m", module, *extra_args, *file_strs]
        commands.append((name, cmd))

    return commands


def run_linters(
    files: list[Path],
    cli_cfg: dict,
    timeout: int,
) -> str:
    """Run all linters and return combined diagnostics."""
    commands = build_commands(files, cli_cfg)
    diagnostics: list[str] = []

    for name, cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            diagnostics.append(f"[{name}] timed out after {timeout}s")
            continue
        except FileNotFoundError:
            diagnostics.append(f"[{name}] runner not found")
            continue

        output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        if result.returncode != 0 and output:
            diagnostics.append(f"[{name}]\n{output}")

    return "\n\n".join(diagnostics)


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    cli_cfg = load_toml("cli_defaults.toml")
    magic_cfg = load_toml("magic_numbers.toml")
    timeout = magic_cfg.get("python_linters", {}).get("timeout_seconds", 120)

    cached = load_cache()
    files, current_hashes = changed_files(cached)

    if not files:
        return

    diagnostics = run_linters(files, cli_cfg, timeout)

    if diagnostics:
        json.dump(
            {
                "decision": "block",
                "reason": f"Python lint errors detected:\n\n{diagnostics}\n\nFix these issues.",
            },
            sys.stdout,
        )
    else:
        save_cache(current_hashes)


if __name__ == "__main__":
    main()
