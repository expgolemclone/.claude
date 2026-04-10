#!/usr/bin/env python3
"""Stop hook: scan all *.py files under cwd for Any type usage."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from any_type_core import check_python


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    cwd = data.get("cwd", "")
    if not cwd:
        return

    violations: list[str] = []
    for py_file in sorted(Path(cwd).rglob("*.py")):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if check_python(text):
            violations.append(str(py_file))

    if violations:
        file_list = "\n".join(f"  - {v}" for v in violations)
        json.dump(
            {
                "decision": "block",
                "reason": (
                    f"Any 型が {len(violations)} 個のファイルに残っています:\n"
                    f"{file_list}\n\n"
                    "具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
