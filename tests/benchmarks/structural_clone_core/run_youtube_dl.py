"""Benchmark: structural clone detection against youtube-dl repo.

Runs all-pairs comparison across all .py files in the youtube-dl repo.
Run:  uv run python tests/benchmarks/structural_clone_core/run_youtube_dl.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from structural_clone_core import (
    FunctionRecord,
    MatchResult,
    StructuralCloneConfig,
    anti_unification_similarity,
    clone_function_record,
    compute_label_weights,
    compute_term_idf,
    cosine_similarity,
    eligible_records,
    is_same_record,
    parse_records,
    stmt_ratio_ok,
)

REPO_DIR = Path(__file__).resolve().parent / "youtube-dl"

CONFIG = StructuralCloneConfig(
    min_stmt_count=1,
    min_ast_node_count=20,
    shortlist_size=8,
    max_report_items=50,
    min_vector_similarity=0.60,
    min_au_similarity=0.82,
    min_stmt_ratio=0.60,
    idf_floor=1.0,
)


def find_python_files(repo: Path) -> list[Path]:
    return sorted(repo.rglob("*.py"))


def collect_all_records(files: list[Path]) -> list[FunctionRecord]:
    all_records: list[FunctionRecord] = []
    for path in files:
        records, ok = parse_records(path)
        if ok:
            all_records.extend(records)
    return all_records


def detect_all_pairs(
    all_eligible: list[FunctionRecord],
    config: StructuralCloneConfig,
) -> list[MatchResult]:
    term_idf = compute_term_idf(all_eligible, config.idf_floor)
    label_weights = compute_label_weights(term_idf)

    matches: list[MatchResult] = []
    seen: set[tuple[str, int, str, int]] = set()

    for source in all_eligible:
        for candidate in all_eligible:
            if is_same_record(source, candidate):
                continue
            if not stmt_ratio_ok(source, candidate, config.min_stmt_ratio):
                continue

            pair_key = (
                min(source["path"], candidate["path"]),
                min(source["lineno"], candidate["lineno"]),
                max(source["path"], candidate["path"]),
                max(source["lineno"], candidate["lineno"]),
            )
            if pair_key in seen:
                continue
            seen.add(pair_key)

            vec_sim = cosine_similarity(source["vector"], candidate["vector"], term_idf)
            if vec_sim < config.min_vector_similarity:
                continue

            au_sim = anti_unification_similarity(
                source["normalized_tree"], candidate["normalized_tree"], label_weights
            )
            if au_sim < config.min_au_similarity:
                continue

            matches.append(
                {
                    "source": clone_function_record(source),
                    "candidate": clone_function_record(candidate),
                    "vector_similarity": vec_sim,
                    "au_similarity": au_sim,
                }
            )

    matches.sort(key=lambda m: (-m["au_similarity"], -m["vector_similarity"]))
    return matches


def relative(path: str) -> str:
    try:
        return str(Path(path).relative_to(REPO_DIR))
    except ValueError:
        return Path(path).name


def main() -> None:
    print(f"=== Structural Clone Benchmark: youtube-dl ===")
    print(f"Repo: {REPO_DIR}")
    print(f"Thresholds: vector >= {CONFIG.min_vector_similarity}, au >= {CONFIG.min_au_similarity}")
    print()

    files = find_python_files(REPO_DIR)
    print(f"Python files: {len(files)}")

    start = time.perf_counter()
    all_records = collect_all_records(files)
    parse_ms = (time.perf_counter() - start) * 1000
    print(f"Functions parsed: {len(all_records)} ({parse_ms:.0f} ms)")

    all_eligible = eligible_records(all_records, CONFIG)
    print(f"Eligible (stmt>={CONFIG.min_stmt_count}, nodes>={CONFIG.min_ast_node_count}): {len(all_eligible)}")
    print()

    start = time.perf_counter()
    matches = detect_all_pairs(all_eligible, CONFIG)
    detect_ms = (time.perf_counter() - start) * 1000

    if matches:
        hdr = f"{'Source':<55} {'Candidate':<55} {'Vec':>5} {'AU':>5}"
        print(hdr)
        print("-" * len(hdr))
        for m in matches:
            src = f"{relative(m['source']['path'])}:{m['source']['lineno']} {m['source']['qualname']}"
            cand = f"{relative(m['candidate']['path'])}:{m['candidate']['lineno']} {m['candidate']['qualname']}"
            print(f"{src:<55} {cand:<55} {m['vector_similarity']:>5.3f} {m['au_similarity']:>5.3f}")
        print()

    print("--- Summary ---")
    print(f"  Eligible functions: {len(all_eligible)}")
    print(f"  Duplicate pairs:    {len(matches)}")
    print(f"  Detection time:     {detect_ms:.0f} ms")


if __name__ == "__main__":
    main()
