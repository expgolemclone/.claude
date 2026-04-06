#!/usr/bin/env python3
"""Stop hook: warn when Google Chrome has 3+ tabs open (memory pressure)."""

import json
import subprocess
import sys

TAB_THRESHOLD: int = 3


def count_chrome_tabs() -> int:
    """Count Chrome renderer processes as a proxy for open tabs."""
    result = subprocess.run(
        ["pgrep", "-af", "chrome.*--type=renderer"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    return len(result.stdout.strip().splitlines())


def main() -> None:
    data: dict = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    tab_count = count_chrome_tabs()
    if tab_count < TAB_THRESHOLD:
        return

    json.dump(
        {
            "decision": "block",
            "reason": (
                f"Chrome のタブが {tab_count} 個開いています（上限 {TAB_THRESHOLD}）。\n"
                "メモリ節約のため不要なタブを閉じてください。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
