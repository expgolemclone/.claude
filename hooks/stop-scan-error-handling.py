#!/usr/bin/env python3
"""Stop hook: scan all *.py files under cwd for error_handling violations.

Enforces two mechanically checkable rules from config/common.toml:
- no_bare_except: except / except Exception / except BaseException
- no_silent_swallow: except handler with no re-raise and no notification
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from error_handling_core import check_python

_SKIP_DIRS: frozenset[str] = frozenset({
    ".venv", "node_modules", "__pycache__", "site-packages", "marketplaces",
})


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    cwd = data.get("cwd", "")
    if not cwd:
        return

    hooks_dir = Path.home() / ".claude" / "hooks"

    all_violations: list[str] = []
    for py_file in sorted(Path(cwd).rglob("*.py")):
        if _SKIP_DIRS & set(py_file.parts):
            continue
        if py_file.is_relative_to(hooks_dir):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for v in check_python(text):
            all_violations.append(f"  {py_file}:{v}")

    if all_violations:
        detail = "\n".join(all_violations)
        json.dump(
            {
                "decision": "block",
                "reason": (
                    f"error_handling 違反が {len(all_violations)} 件見つかりました:\n"
                    f"{detail}\n\n"
                    "no_bare_except: 具体的な例外型を指定してください。\n"
                    "no_silent_swallow: ログ出力か再送出してください。"
                ),
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
