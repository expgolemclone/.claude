#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): warn about fallback patterns in Python files.

Per-project configuration is read from ``config/scan_fallbacks.toml``
relative to the current working directory.  If the config file does not
exist the hook is silently skipped (project has not opted in).

Informational only (stderr).  Enforcement of no_bare_except /
no_silent_swallow is handled by stop-scan-error-handling.py.
"""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scan_fallbacks_core import config_to_params, load_toml_config, scan_file

    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    project_root = Path.cwd()
    cfg = load_toml_config(project_root)
    if not cfg:
        return

    scan_roots, exclude_dirs, fn_names, fn_prefixes = config_to_params(cfg)

    try:
        rel = os.path.relpath(file_path, project_root)
    except ValueError:
        return

    parts = Path(rel).parts
    if not parts or parts[0] not in scan_roots:
        return
    if any(p in exclude_dirs for p in parts):
        return

    findings = scan_file(
        Path(file_path),
        rel_display=rel,
        fn_names=fn_names,
        fn_prefixes=fn_prefixes,
    )
    if not findings:
        return

    details = "\n".join(f"  {f}" for f in findings)
    print(
        f"[info] fallback パターンが検出されました:\n{details}\n"
        "fail_fast ルールに基づき文脈判断してください。"
        "正当な用途（optional dependency, 設定のデフォルト値等）は問題ありません。",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
