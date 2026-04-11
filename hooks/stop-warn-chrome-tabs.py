#!/usr/bin/env python3
"""Stop hook: warn when system memory usage exceeds a threshold.

Reads /proc/meminfo and triggers when
(MemTotal - MemAvailable) / MemTotal exceeds MEM_USAGE_THRESHOLD.
"""

import json
import sys

MEM_USAGE_THRESHOLD: float = 0.70


def read_memory_usage_ratio() -> float:
    """Return system memory usage ratio in [0.0, 1.0]."""
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    try:
                        values[key] = int(rest.split()[0])
                    except (IndexError, ValueError):
                        return 0.0
                    if len(values) == 2:
                        break
    except (FileNotFoundError, PermissionError):
        return 0.0
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if total <= 0:
        return 0.0
    return (total - available) / total


def main() -> None:
    data: dict = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    usage_ratio = read_memory_usage_ratio()
    if usage_ratio <= MEM_USAGE_THRESHOLD:
        return

    json.dump(
        {
            "decision": "block",
            "reason": (
                f"システムメモリ使用率が {usage_ratio * 100:.0f}% です"
                f"（上限 {MEM_USAGE_THRESHOLD * 100:.0f}%）。\n"
                "メモリ節約のため不要なタブ・ウィンドウを閉じてください。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
