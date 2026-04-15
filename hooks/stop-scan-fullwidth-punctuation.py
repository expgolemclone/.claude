#!/usr/bin/env python3
"""Stop hook: scan all files under cwd for fullwidth punctuation."""

import json
import re
import sys
from pathlib import Path

_FULLWIDTH_PUNCTUATION = re.compile(
    r'[。\、，；：！？「」『』【】〈〉《》〔〕（）]'
)
_NOQA_MARKER = "# noqa: fullwidth-punctuation"
_SKIP_DIRS = frozenset({
    ".venv", "node_modules", "__pycache__", "site-packages",
    ".git", ".claude", "dist", "build",
})


def _check_file(path: Path) -> list[str]:
    """Return list of lines with fullwidth punctuation."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    violations: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if _NOQA_MARKER in line:
            continue
        if _FULLWIDTH_PUNCTUATION.search(line):
            found = _FULLWIDTH_PUNCTUATION.findall(line)
            violations.append(f"{path}:{lineno} {repr(found)}")
    return violations


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    cwd = data.get("cwd", "")
    if not cwd:
        return

    all_violations: list[str] = []
    for file_path in sorted(Path(cwd).rglob("*")):
        if not file_path.is_file():
            continue
        if _SKIP_DIRS & set(file_path.parts):
            continue

        all_violations.extend(_check_file(file_path))

    if all_violations:
        detail = "\n".join(all_violations[:50])
        if len(all_violations) > 50:
            detail += f"\n  ... 他 {len(all_violations) - 50} 件"
        json.dump(
            {
                "decision": "block",
                "reason": (
                    f"全角句読点が {len(all_violations)} 箇所で見つかりました:\n"
                    f"{detail}\n\n"
                    f"半角記号を使用してください。"
                    f"除外する場合は行末に {_NOQA_MARKER} を追加してください。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
