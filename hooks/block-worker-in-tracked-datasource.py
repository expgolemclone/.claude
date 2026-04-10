#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): block worker orchestration in tracked datasource files.

Files in datasources/ that are tracked by hash-based cache invalidation
should contain only extraction/parsing logic.  Worker orchestration
(threading, progress counters, stats management) and DB query functions
belong in separate non-tracked modules so that changes to them do not
trigger unnecessary cache invalidation.
"""

import json
import os
import re
import sys

# Patterns that indicate worker orchestration or DB query logic
_PROHIBITED_PATTERNS: list[tuple[str, str]] = [
    # Worker function definitions
    (r"^def \w+_worker\(", "worker function definition"),
    # Threading (only needed for worker orchestration)
    (r"^import threading\b", "threading import"),
    (r"^\s*from threading import\b", "threading import"),
    (r"\bthreading\.Lock\b", "threading.Lock usage"),
    # Worker stats / progress management
    (r"\bstats_lock\b", "worker stats lock usage"),
    (r"\bcounter\[0\]", "worker progress counter usage"),
    (r"^\s*stats\[", "worker stats dict mutation"),
    (r"\bprint\(f\"\[", "worker progress print"),
    # DB connection management (parsing modules should not open connections)
    (r"\bget_connection\(\)", "DB connection in datasource"),
    (r"\bupsert_financial_items_bulk\b", "DB bulk upsert in datasource"),
    (r"\bupsert_price\b", "DB upsert_price in datasource"),
    (r"\bupsert_stock\b", "DB upsert_stock in datasource"),
    # Concurrent execution
    (r"\bThreadPoolExecutor\b", "ThreadPoolExecutor in datasource"),
    (r"\bconcurrent\.futures\b", "concurrent.futures in datasource"),
    # Skip filter / DB query functions (belong in repository.py)
    (r"^\s*SELECT DISTINCT ticker FROM", "SQL query in datasource"),
    (r"^\s*SELECT 1 FROM financial_items", "skip-check query in datasource"),
]

_NOQA_TAG = "# noqa: tracked-file"


def _find_violations(source: str) -> list[tuple[int, str, str]]:
    """Return (lineno, matched_text, reason) for prohibited patterns."""
    violations: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        if _NOQA_TAG in line:
            continue
        for pattern, reason in _PROHIBITED_PATTERNS:
            if re.search(pattern, line):
                violations.append((lineno, line.strip(), reason))
                break
    return violations


def _is_tracked_datasource(file_path: str) -> bool:
    """Return True if file is in a datasources/ directory with cache_invalidation."""
    norm = file_path.replace("\\", "/")
    if "/datasources/" not in norm or not norm.endswith(".py"):
        return False
    datasources_dir = os.path.dirname(file_path)
    parent_dir = os.path.dirname(datasources_dir)
    return os.path.isfile(os.path.join(parent_dir, "cache_invalidation.py"))


def main() -> None:
    data = json.load(sys.stdin)
    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not _is_tracked_datasource(file_path):
        return

    if not os.path.isfile(file_path):
        return

    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    violations = _find_violations(source)
    if not violations:
        return

    details = "\n".join(
        f"  L{lineno}: {reason}: {text}" for lineno, text, reason in violations[:5]
    )
    basename = os.path.basename(file_path)
    json.dump(
        {
            "decision": "block",
            "reason": (
                f"{basename} はキャッシュ無効化のハッシュ追跡対象ファイルです。\n"
                f"ワーカー制御・DB問い合わせ等のロジックを含めないでください:\n"
                f"{details}\n"
                "worker.py や db/repository.py に配置してください "
                f"({_NOQA_TAG} で除外可)。"
            ),
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
