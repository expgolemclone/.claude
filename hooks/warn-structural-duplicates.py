#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): warn about structural duplicate Python functions."""

import json
import sys
from pathlib import Path

from structural_clone_core import (
    detect_structural_duplicates,
    load_config,
    relative_path,
    resolve_repo_root,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAGIC_NUMBERS_PATH = PROJECT_ROOT / "config" / "magic_numbers.toml"


def main() -> None:
    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path.endswith(".py"):
        return

    current_file = Path(file_path).resolve()
    if not current_file.is_file():
        return

    repo_root = resolve_repo_root(current_file)
    if repo_root is None:
        return

    config = load_config(MAGIC_NUMBERS_PATH)
    result = detect_structural_duplicates(repo_root, current_file, config)
    if result is None:
        return

    matches, _ = result
    if not matches:
        return

    lines = []
    for match in matches:
        source = match["source"]
        candidate = match["candidate"]
        lines.append(
            "  - "
            f"{relative_path(source['path'], repo_root)}:{source['lineno']} `{source['qualname']}`"
            " ~= "
            f"{relative_path(candidate['path'], repo_root)}:{candidate['lineno']} `{candidate['qualname']}`"
            f" (vector={match['vector_similarity']:.3f}, au={match['au_similarity']:.3f})"
        )

    json.dump(
        {
            "decision": "stop",
            "reason": (
                "構造的に重複した Python 関数候補が見つかりました。\n"
                + "\n".join(lines)
                + "\n共通化または抽象化を検討してください。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
