#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): block individual file entries when a wildcard pattern should be used.

Ensures .gitignore uses `!*.py` and `!*.toml` instead of listing individual files
like `!setup.py` or `!pyproject.toml`.
"""

import json
import os
import re
import sys

# extension -> required wildcard pattern
REQUIRED_WILDCARDS: dict[str, str] = {
    ".py": "!*.py",
    ".toml": "!*.toml",
}


def _find_individual_entries(content: str) -> list[str]:
    """Return individual file entries that should use a wildcard instead."""
    violations: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Match negation patterns like `!setup.py`, `!pyproject.toml`
        m = re.match(r"^!([^/*]+)$", stripped)
        if not m:
            continue
        filename = m.group(1)
        for ext, wildcard in REQUIRED_WILDCARDS.items():
            if filename.endswith(ext) and stripped != wildcard:
                violations.append(f"  {stripped} → {wildcard} を使用してください")
    return violations


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if os.path.basename(file_path) != ".gitignore":
        return

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return

    violations = _find_individual_entries(content)
    if not violations:
        return

    json.dump(
        {
            "decision": "block",
            "reason": (
                ".gitignore で個別ファイル指定が検出されました。ワイルドカードを使用してください:\n"
                + "\n".join(violations)
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
