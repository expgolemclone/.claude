#!/usr/bin/env python3
"""Stop hook: warn when Google Chrome is under memory pressure.

Counts Chrome windows via Hyprland and sums renderer RSS via /proc,
because renderer-process count diverges from actual tab count due to
site isolation, spare renderers, and out-of-process iframes.
"""

import json
import subprocess
import sys

WINDOW_THRESHOLD: int = 3
RSS_THRESHOLD_MB: int = 2048


def count_chrome_windows() -> int:
    """Count top-level Chrome windows reported by Hyprland."""
    result = subprocess.run(
        ["hyprctl", "clients", "-j"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    try:
        clients = json.loads(result.stdout)
    except json.JSONDecodeError:
        return 0
    return sum(
        1
        for c in clients
        if "chrome" in (c.get("class") or "").lower()
        or "chrome" in (c.get("initialClass") or "").lower()
    )


def sum_chrome_renderer_rss_mb() -> int:
    """Sum RSS (MB) of all Chrome renderer processes, including spares."""
    pgrep = subprocess.run(
        ["pgrep", "-f", "chrome.*--type=renderer"],
        capture_output=True,
        text=True,
    )
    if pgrep.returncode != 0:
        return 0
    pids = [p for p in pgrep.stdout.split() if p.isdigit()]
    if not pids:
        return 0
    total_kb = 0
    for pid in pids:
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        total_kb += int(line.split()[1])
                        break
        except (FileNotFoundError, PermissionError, ValueError):
            # Process died between pgrep and read, or is inaccessible.
            continue
    return total_kb // 1024


def main() -> None:
    data: dict = json.load(sys.stdin)

    if data.get("stop_hook_active"):
        return

    if data.get("permission_mode") == "plan":
        return

    window_count = count_chrome_windows()
    rss_mb = sum_chrome_renderer_rss_mb()

    window_over = window_count >= WINDOW_THRESHOLD
    rss_over = rss_mb >= RSS_THRESHOLD_MB

    if not window_over and not rss_over:
        return

    reasons = []
    if window_over:
        reasons.append(
            f"Chrome ウィンドウが {window_count} 個開いています（上限 {WINDOW_THRESHOLD}）"
        )
    if rss_over:
        reasons.append(
            f"Chrome renderer の合計メモリが {rss_mb} MB です（上限 {RSS_THRESHOLD_MB} MB）"
        )

    json.dump(
        {
            "decision": "block",
            "reason": (
                "\n".join(reasons) + "\nメモリ節約のため不要なタブ・ウィンドウを閉じてください。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
