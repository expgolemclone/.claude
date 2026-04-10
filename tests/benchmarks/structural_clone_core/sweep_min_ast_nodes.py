"""Controlled experiment: sweep min_ast_node_count to find the optimal threshold.

Measures both synthetic and public-apis benchmarks across a range of values,
then reports Precision/Recall/F1 and ground-truth hit rates.

Run:  uv run python tests/benchmarks/structural_clone_core/sweep_min_ast_nodes.py
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
HOOKS_DIR = ROOT_DIR / "hooks"
TESTS_DIR = ROOT_DIR / "tests"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(TESTS_DIR))

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
from bench_structural_clone import CASES, evaluate_pair

REPO_DIR = Path(__file__).resolve().parent / "public-apis"

SWEEP_VALUES = [15, 18, 20, 22, 24, 25, 28, 30]

BASE_CONFIG = StructuralCloneConfig(
    min_stmt_count=1,
    min_ast_node_count=25,
    shortlist_size=8,
    max_report_items=50,
    min_vector_similarity=0.60,
    min_au_similarity=0.82,
    min_stmt_ratio=0.60,
    idf_floor=1.0,
)

GROUND_TRUTH_PAIRS: list[tuple[str, str]] = [
    ("test_check_https_with_valid_https", "test_check_cors_with_valid_cors"),
    ("test_check_https_with_invalid_https", "test_check_cors_with_invalid_cors"),
    ("test_check_title_with_correct_title", "test_check_description_with_correct_description"),
]


def config_with_node_count(node_count: int) -> StructuralCloneConfig:
    return StructuralCloneConfig(
        min_stmt_count=BASE_CONFIG.min_stmt_count,
        min_ast_node_count=node_count,
        shortlist_size=BASE_CONFIG.shortlist_size,
        max_report_items=BASE_CONFIG.max_report_items,
        min_vector_similarity=BASE_CONFIG.min_vector_similarity,
        min_au_similarity=BASE_CONFIG.min_au_similarity,
        min_stmt_ratio=BASE_CONFIG.min_stmt_ratio,
        idf_floor=BASE_CONFIG.idf_floor,
    )


# --- Synthetic benchmark ---


@dataclass(frozen=True)
class SyntheticResult:
    node_count: int
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2.0 * p * r / (p + r) if (p + r) > 0.0 else 0.0


def run_synthetic(config: StructuralCloneConfig) -> SyntheticResult:
    tp = fp = tn = fn = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for case in CASES:
            src_path = tmp_path / f"{case.label}_source.py"
            cand_path = tmp_path / f"{case.label}_candidate.py"
            src_path.write_text(case.source_code, encoding="utf-8")
            cand_path.write_text(case.candidate_code, encoding="utf-8")

            vec_sim, au_sim = evaluate_pair(src_path, cand_path, config)
            detected = vec_sim >= config.min_vector_similarity and au_sim >= config.min_au_similarity

            if case.expected_match and detected:
                tp += 1
            elif case.expected_match and not detected:
                fn += 1
            elif not case.expected_match and detected:
                fp += 1
            else:
                tn += 1

    return SyntheticResult(node_count=config.min_ast_node_count, tp=tp, fp=fp, tn=tn, fn=fn)


# --- public-apis benchmark ---


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


def qualname_match(qualname: str, pattern: str) -> bool:
    return qualname.endswith(pattern) or qualname == pattern


def is_ground_truth(match: MatchResult) -> bool:
    src_q = match["source"]["qualname"]
    cand_q = match["candidate"]["qualname"]
    for left, right in GROUND_TRUTH_PAIRS:
        if (qualname_match(src_q, left) and qualname_match(cand_q, right)) or (
            qualname_match(src_q, right) and qualname_match(cand_q, left)
        ):
            return True
    return False


@dataclass(frozen=True)
class PublicApisResult:
    node_count: int
    eligible_count: int
    total_pairs: int
    gt_hits: int
    gt_total: int
    new_pairs: list[MatchResult]


def run_public_apis(
    all_records: list[FunctionRecord],
    config: StructuralCloneConfig,
) -> PublicApisResult:
    all_eligible = eligible_records(all_records, config)
    matches = detect_all_pairs(all_eligible, config)

    gt_hits = sum(1 for m in matches if is_ground_truth(m))
    new_pairs = [m for m in matches if not is_ground_truth(m)]

    return PublicApisResult(
        node_count=config.min_ast_node_count,
        eligible_count=len(all_eligible),
        total_pairs=len(matches),
        gt_hits=gt_hits,
        gt_total=len(GROUND_TRUTH_PAIRS),
        new_pairs=new_pairs,
    )


def relative(path: str) -> str:
    try:
        return str(Path(path).relative_to(REPO_DIR))
    except ValueError:
        return Path(path).name


def main() -> None:
    print("=== Sweep: min_ast_node_count ===")
    print(f"Values: {SWEEP_VALUES}")
    print()

    # Pre-parse public-apis once (parsing is threshold-independent)
    files = find_python_files(REPO_DIR)
    all_records = collect_all_records(files)
    print(f"public-apis: {len(files)} files, {len(all_records)} functions parsed")
    print()

    synthetic_results: list[SyntheticResult] = []
    public_results: list[PublicApisResult] = []

    for node_count in SWEEP_VALUES:
        config = config_with_node_count(node_count)
        synthetic_results.append(run_synthetic(config))
        public_results.append(run_public_apis(all_records, config))

    # --- Synthetic table ---
    print("--- Synthetic Benchmark ---")
    print(f"{'nodes':>5}  {'TP':>2}  {'FP':>2}  {'TN':>2}  {'FN':>2}  {'Prec':>6}  {'Rec':>6}  {'F1':>6}")
    for r in synthetic_results:
        print(f"{r.node_count:>5}  {r.tp:>2}  {r.fp:>2}  {r.tn:>2}  {r.fn:>2}  {r.precision:>6.3f}  {r.recall:>6.3f}  {r.f1:>6.3f}")
    print()

    # --- public-apis table ---
    print("--- public-apis Benchmark ---")
    print(f"{'nodes':>5}  {'Eligible':>8}  {'Pairs':>5}  {'GT-Hit':>6}  {'GT-Miss':>7}  {'New':>3}")
    for r in public_results:
        gt_miss = r.gt_total - r.gt_hits
        print(
            f"{r.node_count:>5}  {r.eligible_count:>8}  {r.total_pairs:>5}  "
            f"{r.gt_hits}/{r.gt_total:>3}    {gt_miss:>5}  {len(r.new_pairs):>3}"
        )
    print()

    # --- New pairs detail ---
    all_new: dict[int, list[MatchResult]] = {}
    for r in public_results:
        if r.new_pairs:
            all_new[r.node_count] = r.new_pairs

    if all_new:
        print("--- New pairs at each threshold (FP candidates) ---")
        for node_count, pairs in sorted(all_new.items()):
            for m in pairs:
                src = f"{relative(m['source']['path'])}:{m['source']['lineno']} {m['source']['qualname']}"
                cand = f"{relative(m['candidate']['path'])}:{m['candidate']['lineno']} {m['candidate']['qualname']}"
                print(
                    f"  nodes={node_count}: {src}  ~  {cand}"
                    f"  (vec={m['vector_similarity']:.3f}, au={m['au_similarity']:.3f})"
                )
        print()

    # --- Recommendation ---
    best = None
    for sr, pr in zip(synthetic_results, public_results):
        if sr.fp > 0:
            continue
        score = sr.f1 + (pr.gt_hits / pr.gt_total if pr.gt_total > 0 else 0.0) - len(pr.new_pairs) * 0.1
        if best is None or score > best[1]:
            best = (sr.node_count, score)

    if best is not None:
        print(f">>> Recommended: min_ast_node_count = {best[0]} (score={best[1]:.3f})")


if __name__ == "__main__":
    main()
