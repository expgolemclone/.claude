"""Accuracy benchmark for the structural clone detection engine.

Measures Precision / Recall / F1 against ground-truth labeled pairs.
Run:  python tests/bench_structural_clone.py
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from structural_clone_core import (
    FunctionRecord,
    StructuralCloneConfig,
    anti_unification_similarity,
    compute_label_weights,
    compute_term_idf,
    cosine_similarity,
    eligible_records,
    parse_records,
)

CONFIG = StructuralCloneConfig(
    min_stmt_count=1,
    min_ast_node_count=25,
    shortlist_size=8,
    max_report_items=3,
    min_vector_similarity=0.60,
    min_au_similarity=0.82,
    min_stmt_ratio=0.60,
    idf_floor=1.0,
)


@dataclass(frozen=True)
class TestCase:
    label: str
    category: str
    source_code: str
    candidate_code: str
    expected_match: bool


@dataclass(frozen=True)
class CaseResult:
    label: str
    category: str
    expected_match: bool
    vector_sim: float
    au_sim: float
    detected: bool

    @property
    def passed(self) -> bool:
        return self.detected == self.expected_match


CASES: list[TestCase] = [
    # ---- TP: exact clone (names differ, body identical) ----
    TestCase(
        label="exact_clone",
        category="TP",
        source_code="""\
def fetch_prices(args: object) -> None:
    pool = resolve_proxy(args)
    conn = get_connection()
    tickers = args.ticker if args.ticker else get_all(conn)
    dispatch(tickers, pool, worker_fn=fetch_worker, label='prices')
""",
        candidate_code="""\
def scrape_data(params: object) -> None:
    pool = resolve_proxy(params)
    conn = get_connection()
    tickers = params.ticker if params.ticker else get_all(conn)
    dispatch(tickers, pool, worker_fn=fetch_worker, label='prices')
""",
        expected_match=True,
    ),
    # ---- TP: near clone (one extra statement) ----
    TestCase(
        label="near_clone_extra_stmt",
        category="TP",
        source_code="""\
def process_batch(items: list[object], config: object) -> object:
    validated = validate_all(items, strict=config.strict)
    filtered = filter_active(validated, since=config.cutoff)
    grouped = group_by_key(filtered, key=config.group_key)
    results = run_pipeline(grouped, workers=config.workers)
    save_results(results, path=config.output_path)
    return results
""",
        candidate_code="""\
def process_batch_v2(items: list[object], config: object) -> object:
    validated = validate_all(items, strict=config.strict)
    filtered = filter_active(validated, since=config.cutoff)
    grouped = group_by_key(filtered, key=config.group_key)
    results = run_pipeline(grouped, workers=config.workers)
    log_summary(results)
    save_results(results, path=config.output_path)
    return results
""",
        expected_match=True,
    ),
    # ---- TP: parameterized clone (call targets differ) ----
    TestCase(
        label="parameterized_clone",
        category="TP",
        source_code="""\
def export_csv(db: object, query: str, path: str) -> None:
    conn = db.connect()
    rows = conn.execute(query)
    data = transform_rows(rows)
    write_output(data, path, fmt='csv')
""",
        candidate_code="""\
def export_json(db: object, query: str, path: str) -> None:
    conn = db.connect()
    rows = conn.execute(query)
    data = transform_rows(rows)
    write_output(data, path, fmt='json')
""",
        expected_match=True,
    ),
    # ---- TP: async/sync clone ----
    TestCase(
        label="async_sync_clone",
        category="TP",
        source_code="""\
def sync_fetch(client: object, url: str, retries: int) -> object:
    response = client.get(url, timeout=retries)
    data = response.json()
    validated = validate_schema(data, strict=True)
    transformed = apply_transforms(validated, normalize=True)
    cached = cache_result(transformed, key=url)
    return process_result(cached)
""",
        candidate_code="""\
async def async_fetch(client: object, url: str, retries: int) -> object:
    response = client.get(url, timeout=retries)
    data = response.json()
    validated = validate_schema(data, strict=True)
    transformed = apply_transforms(validated, normalize=True)
    cached = cache_result(transformed, key=url)
    return process_result(cached)
""",
        expected_match=True,
    ),
    # ---- TP: method in different class ----
    TestCase(
        label="method_clone_diff_class",
        category="TP",
        source_code="""\
class ReportA:
    def generate(self, params: object) -> object:
        data = self.query_data(params)
        filtered = self.apply_filters(data, params)
        grouped = self.group_results(filtered, key=params.group)
        formatted = self.format_output(grouped)
        validated = self.validate_output(formatted)
        return self.finalize(validated)
""",
        candidate_code="""\
class ReportB:
    def generate(self, params: object) -> object:
        data = self.query_data(params)
        filtered = self.apply_filters(data, params)
        grouped = self.group_results(filtered, key=params.group)
        formatted = self.format_output(grouped)
        validated = self.validate_output(formatted)
        return self.finalize(validated)
""",
        expected_match=True,
    ),
    # ---- TP: clone with variable rename ----
    TestCase(
        label="rename_clone",
        category="TP",
        source_code="""\
def build_report(config: object, db: object) -> object:
    connection = db.connect()
    raw = connection.fetch(config.query)
    cleaned = sanitize(raw)
    aggregated = aggregate(cleaned, config.group_by)
    return render(aggregated)
""",
        candidate_code="""\
def create_summary(settings: object, database: object) -> object:
    connection = database.connect()
    raw = connection.fetch(settings.query)
    cleaned = sanitize(raw)
    aggregated = aggregate(cleaned, settings.group_by)
    return render(aggregated)
""",
        expected_match=True,
    ),
    # ---- TP: for-loop clone (few top-level stmts, many AST nodes) ----
    TestCase(
        label="forloop_clone",
        category="TP",
        source_code="""\
def validate_https(entries: list[str], keys: list[str]) -> None:
    for entry in entries:
        result = check_https(0, entry)
        assert_is_instance(result, list)
        assert_equal(len(result), 1)
        msg = result[0]
        expected = format_error(entry, kind='https')
        assert_is_instance(msg, str)
        assert_equal(msg, expected)
""",
        candidate_code="""\
def validate_cors(entries: list[str], keys: list[str]) -> None:
    for entry in entries:
        result = check_cors(0, entry)
        assert_is_instance(result, list)
        assert_equal(len(result), 1)
        msg = result[0]
        expected = format_error(entry, kind='cors')
        assert_is_instance(msg, str)
        assert_equal(msg, expected)
""",
        expected_match=True,
    ),
    # ---- TN: completely different logic ----
    TestCase(
        label="different_logic",
        category="TN",
        source_code="""\
def merge_sort(arr: list[int]) -> list[int]:
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)
""",
        candidate_code="""\
def parse_config(path: str) -> object:
    with open(path) as f:
        raw = f.read()
    tokens = tokenize(raw)
    ast = build_ast(tokens)
    return validate_config(ast)
""",
        expected_match=False,
    ),
    # ---- TN: same API, different control flow ----
    TestCase(
        label="same_api_diff_flow",
        category="TN",
        source_code="""\
def sequential_upload(files: list[str], client: object) -> object:
    results: list[object] = []
    for f in files:
        resp = client.upload(f)
        results.append(resp)
    return aggregate_results(results)
""",
        candidate_code="""\
def conditional_upload(files: list[str], client: object) -> object:
    if not files:
        return empty_result()
    first = client.upload(files[0])
    if first.failed:
        raise UploadError(first)
    return first
""",
        expected_match=False,
    ),
    # ---- TN: similar shape but different operations ----
    TestCase(
        label="similar_shape_diff_ops",
        category="TN",
        source_code="""\
def compute_stats(values: list[float]) -> tuple[float, float]:
    total = sum(values)
    count = len(values)
    mean = total / count
    variance = sum((x - mean) ** 2 for x in values) / count
    return mean, variance
""",
        candidate_code="""\
def format_table(rows: list[object]) -> tuple[str, str, str]:
    header = build_header(rows)
    widths = compute_widths(rows)
    body = render_body(rows, widths)
    footer = render_footer(rows, widths)
    return header, body, footer
""",
        expected_match=False,
    ),
    # ---- TN: small functions below threshold ----
    TestCase(
        label="below_threshold",
        category="TN",
        source_code="""\
def add(a: int, b: int) -> int:
    return a + b
""",
        candidate_code="""\
def sub(a: int, b: int) -> int:
    return a - b
""",
        expected_match=False,
    ),
    # ---- TN: different iteration patterns ----
    TestCase(
        label="diff_iteration",
        category="TN",
        source_code="""\
def collect_with_loop(items: list[object], predicate: object) -> object:
    result: list[object] = []
    for item in items:
        if predicate(item):
            result.append(transform(item))
    return finalize(result)
""",
        candidate_code="""\
def collect_recursive(items: list[object], predicate: object, acc: list[object] | None = None) -> object:
    if acc is None:
        acc = []
    if not items:
        return finalize(acc)
    head, *tail = items
    if predicate(head):
        acc.append(transform(head))
    return collect_recursive(tail, predicate, acc)
""",
        expected_match=False,
    ),
]


def evaluate_pair(
    source_path: Path,
    candidate_path: Path,
    config: StructuralCloneConfig,
) -> tuple[float, float]:
    """Compute vector and AU similarity for the first eligible function in each file."""
    src_records, _ = parse_records(source_path)
    cand_records, _ = parse_records(candidate_path)

    all_records: list[FunctionRecord] = src_records + cand_records
    all_eligible = eligible_records(all_records, config)

    src_eligible = [r for r in all_eligible if r["path"] == str(source_path.resolve())]
    cand_eligible = [r for r in all_eligible if r["path"] == str(candidate_path.resolve())]

    if not src_eligible or not cand_eligible:
        return 0.0, 0.0

    src_rec = src_eligible[0]
    cand_rec = cand_eligible[0]

    term_idf = compute_term_idf(all_eligible, config.idf_floor)
    label_weights = compute_label_weights(term_idf)

    vec_sim = cosine_similarity(src_rec["vector"], cand_rec["vector"], term_idf)
    au_sim = anti_unification_similarity(
        src_rec["normalized_tree"], cand_rec["normalized_tree"], label_weights
    )
    return vec_sim, au_sim


def run_benchmark() -> list[CaseResult]:
    results: list[CaseResult] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for case in CASES:
            src_path = tmp_path / f"{case.label}_source.py"
            cand_path = tmp_path / f"{case.label}_candidate.py"
            src_path.write_text(case.source_code, encoding="utf-8")
            cand_path.write_text(case.candidate_code, encoding="utf-8")

            vec_sim, au_sim = evaluate_pair(src_path, cand_path, CONFIG)
            detected = vec_sim >= CONFIG.min_vector_similarity and au_sim >= CONFIG.min_au_similarity

            results.append(
                CaseResult(
                    label=case.label,
                    category=case.category,
                    expected_match=case.expected_match,
                    vector_sim=vec_sim,
                    au_sim=au_sim,
                    detected=detected,
                )
            )
    return results


def print_report(results: list[CaseResult]) -> None:
    print("\n=== Structural Clone Detection Accuracy Benchmark ===")
    print(f"Thresholds: vector >= {CONFIG.min_vector_similarity}, au >= {CONFIG.min_au_similarity}")
    print()

    hdr = f"{'Case':<30} {'Expect':>6} {'Vec.Sim':>8} {'AU Sim':>8} {'Detect':>7} {'Result':>7}"
    print(hdr)
    print("-" * len(hdr))

    tp = fp = tn = fn = 0
    for r in results:
        if r.expected_match and r.detected:
            tp += 1
        elif r.expected_match and not r.detected:
            fn += 1
        elif not r.expected_match and r.detected:
            fp += 1
        else:
            tn += 1

        detect_str = "YES" if r.detected else "NO"
        result_str = "PASS" if r.passed else "FAIL"
        print(
            f"{r.label:<30} {r.category:>6} {r.vector_sim:>8.3f} {r.au_sim:>8.3f}"
            f" {detect_str:>7} {result_str:>7}"
        )

    print()
    print("--- Summary ---")
    print(f"  TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0.0 else 0.0
    print(f"  Precision: {precision:.3f}  Recall: {recall:.3f}  F1: {f1:.3f}")


def main() -> None:
    results = run_benchmark()
    print_report(results)


if __name__ == "__main__":
    main()
