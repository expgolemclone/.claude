#!/usr/bin/env python3
"""Stop hook: セッション終了時に Clawd マスコット非表示パッチを自動適用する."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "patch-clawd-mascot.py"


def main() -> None:
    data = json.load(sys.stdin)

    if data.get("permission_mode") == "plan":
        return

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    output = result.stdout.strip()
    if output and "パッチ適用" in output:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": f"[auto] clawd mascot patch:\n{output}",
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
