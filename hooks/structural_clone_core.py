"""Shared core for Python structural clone detection hooks."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypedDict

from project_root import find_git_root


CACHE_SCHEMA_VERSION = "1"
CACHE_FILENAME = "structural-clone-index.json"


class NormalizedNode(TypedDict):
    """Normalized AST node used for vectoring and anti-unification."""

    label: str
    children: list["NormalizedNode"]


class FunctionRecord(TypedDict):
    """Cached representation for one function."""

    path: str
    qualname: str
    lineno: int
    end_lineno: int
    stmt_count: int
    ast_node_count: int
    vector: dict[str, float]
    normalized_tree: NormalizedNode


class FileCacheEntry(TypedDict):
    """Per-file cache entry."""

    sha256: str
    records: list[FunctionRecord]


class StructuralCloneCache(TypedDict):
    """Top-level cache payload."""

    schema_version: str
    repo_root: str
    files: dict[str, FileCacheEntry]


class MatchResult(TypedDict):
    """Detected duplicate pair."""

    source: FunctionRecord
    candidate: FunctionRecord
    vector_similarity: float
    au_similarity: float


@dataclass(frozen=True)
class StructuralCloneConfig:
    """Runtime thresholds for clone detection."""

    min_stmt_count: int
    min_ast_node_count: int
    shortlist_size: int
    max_report_items: int
    min_vector_similarity: float
    min_au_similarity: float
    min_stmt_ratio: float
    idf_floor: float


def load_config(path: Path) -> StructuralCloneConfig:
    """Load structural clone thresholds from magic_numbers.toml."""
    with open(path, "rb") as f:
        loaded: object = tomllib.load(f)
    if not isinstance(loaded, dict):
        raise ValueError("magic_numbers.toml must contain a top-level table")
    section_obj: object = loaded.get("structural_clone_hook")
    if not isinstance(section_obj, dict):
        raise ValueError("missing [structural_clone_hook] config section")
    return StructuralCloneConfig(
        min_stmt_count=_read_int(section_obj, "min_stmt_count"),
        min_ast_node_count=_read_int(section_obj, "min_ast_node_count"),
        shortlist_size=_read_int(section_obj, "shortlist_size"),
        max_report_items=_read_int(section_obj, "max_report_items"),
        min_vector_similarity=_read_float(section_obj, "min_vector_similarity"),
        min_au_similarity=_read_float(section_obj, "min_au_similarity"),
        min_stmt_ratio=_read_float(section_obj, "min_stmt_ratio"),
        idf_floor=_read_float(section_obj, "idf_floor"),
    )


def _read_int(section: dict[str, object], key: str) -> int:
    value: object = section.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _read_float(section: dict[str, object], key: str) -> float:
    value: object = section.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def empty_cache(repo_root: str) -> StructuralCloneCache:
    """Build an empty cache payload."""
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "repo_root": repo_root,
        "files": {},
    }


def file_sha256(path: Path) -> str:
    """Compute SHA-256 for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_cache_payload(
    schema_version: str,
    repo_root: str,
    records_by_file: Mapping[str, list[FunctionRecord]],
) -> StructuralCloneCache:
    """Build a cache payload from function records."""
    files: dict[str, FileCacheEntry] = {}
    for path_str, records in records_by_file.items():
        path = Path(path_str)
        files[str(path.resolve())] = {
            "sha256": file_sha256(path),
            "records": [clone_function_record(record) for record in records],
        }
    return {
        "schema_version": schema_version,
        "repo_root": str(Path(repo_root).resolve()),
        "files": files,
    }


def save_cache(path: Path, payload: StructuralCloneCache) -> None:
    """Persist cache to disk atomically via temp-file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        Path(tmp_path).replace(path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def load_cache(path: Path) -> StructuralCloneCache:
    """Load cache from disk, returning an empty payload on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            raw_data: object = json.load(f)
    except (OSError, json.JSONDecodeError):
        return empty_cache("")

    parsed = _coerce_cache(raw_data)
    if parsed is None:
        return empty_cache("")
    return parsed


def _coerce_cache(raw_data: object) -> StructuralCloneCache | None:
    if not isinstance(raw_data, dict):
        return None
    schema_version = raw_data.get("schema_version")
    repo_root = raw_data.get("repo_root")
    files_obj = raw_data.get("files")
    if not isinstance(schema_version, str) or not isinstance(repo_root, str) or not isinstance(files_obj, dict):
        return None

    files: dict[str, FileCacheEntry] = {}
    for key, value in files_obj.items():
        if not isinstance(key, str):
            return None
        entry = _coerce_file_cache_entry(value)
        if entry is None:
            return None
        files[key] = entry

    return {
        "schema_version": schema_version,
        "repo_root": repo_root,
        "files": files,
    }


def _coerce_file_cache_entry(value: object) -> FileCacheEntry | None:
    if not isinstance(value, dict):
        return None
    sha256 = value.get("sha256")
    records_obj = value.get("records")
    if not isinstance(sha256, str) or not isinstance(records_obj, list):
        return None

    records: list[FunctionRecord] = []
    for item in records_obj:
        record = _coerce_function_record(item)
        if record is None:
            return None
        records.append(record)
    return {"sha256": sha256, "records": records}


def _coerce_function_record(value: object) -> FunctionRecord | None:
    if not isinstance(value, dict):
        return None

    path = value.get("path")
    qualname = value.get("qualname")
    lineno = value.get("lineno")
    end_lineno = value.get("end_lineno")
    stmt_count = value.get("stmt_count")
    ast_node_count = value.get("ast_node_count")
    vector_obj = value.get("vector")
    normalized_tree_obj = value.get("normalized_tree")

    if not isinstance(path, str) or not isinstance(qualname, str):
        return None
    if not isinstance(lineno, int) or not isinstance(end_lineno, int):
        return None
    if not isinstance(stmt_count, int) or not isinstance(ast_node_count, int):
        return None
    vector = _coerce_vector(vector_obj)
    normalized_tree = _coerce_normalized_node(normalized_tree_obj)
    if vector is None or normalized_tree is None:
        return None

    return {
        "path": path,
        "qualname": qualname,
        "lineno": lineno,
        "end_lineno": end_lineno,
        "stmt_count": stmt_count,
        "ast_node_count": ast_node_count,
        "vector": vector,
        "normalized_tree": normalized_tree,
    }


def _coerce_vector(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, (int, float)):
            return None
        result[key] = float(item)
    return result


def _coerce_normalized_node(value: object) -> NormalizedNode | None:
    if not isinstance(value, dict):
        return None
    label = value.get("label")
    children_obj = value.get("children")
    if not isinstance(label, str) or not isinstance(children_obj, list):
        return None
    children: list[NormalizedNode] = []
    for child in children_obj:
        parsed = _coerce_normalized_node(child)
        if parsed is None:
            return None
        children.append(parsed)
    return {"label": label, "children": children}


def get_cached_records_for_file(cache: StructuralCloneCache, file_path: Path) -> list[FunctionRecord] | None:
    """Return cached records if the file hash still matches."""
    key = str(file_path.resolve())
    entry = cache["files"].get(key)
    if entry is None or not file_path.exists():
        return None
    if entry["sha256"] != file_sha256(file_path):
        return None
    return [clone_function_record(record) for record in entry["records"]]


def clone_function_record(record: FunctionRecord) -> FunctionRecord:
    """Deep-copy a function record."""
    return {
        "path": record["path"],
        "qualname": record["qualname"],
        "lineno": record["lineno"],
        "end_lineno": record["end_lineno"],
        "stmt_count": record["stmt_count"],
        "ast_node_count": record["ast_node_count"],
        "vector": dict(record["vector"]),
        "normalized_tree": clone_normalized_node(record["normalized_tree"]),
    }


def clone_normalized_node(node: NormalizedNode) -> NormalizedNode:
    """Deep-copy a normalized node."""
    return {
        "label": node["label"],
        "children": [clone_normalized_node(child) for child in node["children"]],
    }


def parse_records(path: Path) -> tuple[list[FunctionRecord], bool]:
    """Parse a Python file into function records."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return [], False

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], False

    collector = _FunctionCollector(path.resolve())
    collector.visit(tree)
    return collector.records, True


class _FunctionCollector(ast.NodeVisitor):
    """Collect normalized function records with nested qualnames."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._stack: list[str] = []
        self.records: list[FunctionRecord] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._collect(node)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._collect(node)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def _collect(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join([*self._stack, node.name]) if self._stack else node.name
        normalized_tree = normalize_function(node)
        self.records.append(
            {
                "path": str(self._path),
                "qualname": qualname,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "stmt_count": len(_body_without_docstring(node.body)),
                "ast_node_count": tree_node_count(normalized_tree),
                "vector": build_vector(normalized_tree),
                "normalized_tree": normalized_tree,
            }
        )


def normalize_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> NormalizedNode:
    """Normalize one function subtree."""
    children = [normalize_node(node.args)]
    children.extend(normalize_node(stmt) for stmt in _body_without_docstring(node.body))
    label = "FunctionDef"
    return {"label": label, "children": children}


def _body_without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and _is_docstring_expr(body[0]):
        return body[1:]
    return body


def _is_docstring_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def normalize_node(node: ast.AST) -> NormalizedNode:
    """Convert an AST node into a normalized tree."""
    label = node_label(node)
    children = [normalize_node(child) for child in child_nodes(node)]
    return {"label": label, "children": children}


def node_label(node: ast.AST) -> str:
    """Return a stable label for one AST node."""
    if isinstance(node, ast.Name):
        return "Name"
    if isinstance(node, ast.arg):
        return "arg"
    if isinstance(node, ast.Attribute):
        return f"Attr[{node.attr}]"
    if isinstance(node, ast.Call):
        return f"Call[{call_target_label(node.func)}]"
    if isinstance(node, ast.keyword):
        return f"kw[{node.arg if node.arg is not None else '**'}]"
    if isinstance(node, ast.BinOp):
        return f"BinOp[{type(node.op).__name__}]"
    if isinstance(node, ast.BoolOp):
        return f"BoolOp[{type(node.op).__name__}]"
    if isinstance(node, ast.UnaryOp):
        return f"UnaryOp[{type(node.op).__name__}]"
    if isinstance(node, ast.Compare):
        op_names = ",".join(type(op).__name__ for op in node.ops)
        return f"Compare[{op_names}]"
    if isinstance(node, ast.Constant):
        return constant_label(node.value)
    return type(node).__name__


def constant_label(value: object) -> str:
    """Bucket constants by coarse type."""
    if value is None:
        return "Const[None]"
    if isinstance(value, bool):
        return "Const[Bool]"
    if isinstance(value, (int, float, complex)):
        return "Const[Num]"
    if isinstance(value, str):
        return "Const[Str]"
    if isinstance(value, bytes):
        return "Const[Bytes]"
    return "Const[Other]"


def call_target_label(node: ast.AST) -> str:
    """Extract a readable callee label for Call nodes."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Lambda):
        return "lambda"
    return type(node).__name__


def child_nodes(node: ast.AST) -> list[ast.AST]:
    """Return relevant child nodes after normalization choices."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [node.args, *_body_without_docstring(node.body)]
    if isinstance(node, ast.arguments):
        children: list[ast.AST] = [*node.posonlyargs, *node.args]
        if node.vararg is not None:
            children.append(node.vararg)
        children.extend(node.kwonlyargs)
        children.extend(default for default in node.defaults)
        children.extend(default for default in node.kw_defaults if default is not None)
        if node.kwarg is not None:
            children.append(node.kwarg)
        return children
    if isinstance(node, ast.Attribute):
        return [node.value]
    if isinstance(node, ast.Call):
        return [*node.args, *node.keywords]
    if isinstance(node, ast.keyword):
        return [node.value]
    if isinstance(node, ast.Compare):
        return [node.left, *node.comparators]
    if isinstance(node, ast.BinOp):
        return [node.left, node.right]
    if isinstance(node, ast.BoolOp):
        return list(node.values)
    if isinstance(node, ast.UnaryOp):
        return [node.operand]
    if isinstance(node, ast.comprehension):
        return [node.target, node.iter, *node.ifs]

    filtered: list[ast.AST] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.expr_context, ast.operator, ast.unaryop, ast.boolop, ast.cmpop)):
            continue
        filtered.append(child)
    return filtered


def tree_node_count(node: NormalizedNode) -> int:
    """Count normalized tree nodes."""
    return 1 + sum(tree_node_count(child) for child in node["children"])


def build_vector(node: NormalizedNode) -> dict[str, float]:
    """Build raw AST vector counts for one normalized tree."""
    vector: dict[str, float] = {}
    _walk_vector(node, vector)
    return vector


def _walk_vector(node: NormalizedNode, vector: dict[str, float]) -> None:
    node_term = f"node:{node['label']}"
    vector[node_term] = vector.get(node_term, 0.0) + 1.0
    for child in node["children"]:
        edge_term = f"edge:{node['label']}->{child['label']}"
        vector[edge_term] = vector.get(edge_term, 0.0) + 1.0
        _walk_vector(child, vector)


def resolve_repo_root(file_path: Path) -> Path | None:
    """Resolve the git repo root for an edited file."""
    root = find_git_root(str(file_path.parent))
    if root is None:
        return None
    return Path(root).resolve()


def list_python_files(repo_root: Path, current_file: Path) -> list[Path]:
    """List tracked .py files in the repo, plus the current file if needed."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "*.py"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    files: list[Path] = []
    seen: set[str] = set()
    for rel_path in result.stdout.splitlines():
        if not rel_path:
            continue
        path = (repo_root / rel_path).resolve()
        key = str(path)
        if path.is_file() and key not in seen:
            files.append(path)
            seen.add(key)

    current_key = str(current_file.resolve())
    if current_file.is_file() and current_key not in seen:
        files.append(current_file.resolve())
    return files


def cache_path_for_repo(repo_root: Path) -> Path:
    """Return the cache file location for a repo."""
    return repo_root / ".cache" / CACHE_FILENAME


def collect_records(
    repo_root: Path,
    current_file: Path,
    cache_path: Path,
) -> tuple[list[FunctionRecord], dict[str, list[FunctionRecord]]]:
    """Collect function records from the repo, reusing cache when possible."""
    cached = load_cache(cache_path)
    if cached["schema_version"] != CACHE_SCHEMA_VERSION or cached["repo_root"] != str(repo_root):
        cached = empty_cache(str(repo_root))

    records_by_file: dict[str, list[FunctionRecord]] = {}
    all_records: list[FunctionRecord] = []
    for path in list_python_files(repo_root, current_file):
        cached_records = get_cached_records_for_file(cached, path)
        if cached_records is not None:
            records = cached_records
        else:
            records, _ = parse_records(path)
        key = str(path.resolve())
        records_by_file[key] = records
        all_records.extend(records)

    return all_records, records_by_file


def eligible_records(records: list[FunctionRecord], config: StructuralCloneConfig) -> list[FunctionRecord]:
    """Filter function records down to comparison candidates."""
    return [
        clone_function_record(record)
        for record in records
        if record["stmt_count"] >= config.min_stmt_count and record["ast_node_count"] >= config.min_ast_node_count
    ]


def detect_structural_duplicates(
    repo_root: Path,
    current_file: Path,
    config: StructuralCloneConfig,
) -> tuple[list[MatchResult], StructuralCloneCache] | None:
    """Detect structural duplicates for functions in the current file."""
    parsed_current, parse_ok = parse_records(current_file)
    if not parse_ok:
        return None

    cache_path = cache_path_for_repo(repo_root)
    all_records, records_by_file = collect_records(repo_root, current_file, cache_path)
    payload = build_cache_payload(
        schema_version=CACHE_SCHEMA_VERSION,
        repo_root=str(repo_root),
        records_by_file=records_by_file,
    )
    save_cache(cache_path, payload)

    all_eligible = eligible_records(all_records, config)
    current_records = [record for record in all_eligible if record["path"] == str(current_file.resolve())]
    if not current_records:
        return [], payload

    term_idf = compute_term_idf(all_eligible, config.idf_floor)
    label_weights = compute_label_weights(term_idf)

    matches: list[MatchResult] = []
    for source in current_records:
        shortlist = shortlist_candidates(source, all_eligible, term_idf, config)
        for candidate, vector_similarity in shortlist:
            au_similarity = anti_unification_similarity(
                source["normalized_tree"],
                candidate["normalized_tree"],
                label_weights,
            )
            if au_similarity < config.min_au_similarity:
                continue
            matches.append(
                {
                    "source": clone_function_record(source),
                    "candidate": clone_function_record(candidate),
                    "vector_similarity": vector_similarity,
                    "au_similarity": au_similarity,
                }
            )

    matches.sort(
        key=lambda item: (
            -item["au_similarity"],
            -item["vector_similarity"],
            item["source"]["path"],
            item["source"]["lineno"],
            item["candidate"]["path"],
            item["candidate"]["lineno"],
        )
    )
    return matches[: config.max_report_items], payload


def compute_term_idf(records: list[FunctionRecord], idf_floor: float) -> dict[str, float]:
    """Compute IDF weights for vector terms."""
    if not records:
        return {}

    doc_freq: dict[str, int] = {}
    for record in records:
        for term in record["vector"]:
            doc_freq[term] = doc_freq.get(term, 0) + 1

    total_docs = float(len(records))
    return {
        term: math.log((total_docs + 1.0) / (float(freq) + 1.0)) + idf_floor
        for term, freq in doc_freq.items()
    }


def compute_label_weights(term_idf: dict[str, float]) -> dict[str, float]:
    """Extract node-label IDF weights from a pre-computed term IDF map."""
    label_weights: dict[str, float] = {}
    for term, weight in term_idf.items():
        if term.startswith("node:"):
            label_weights[term.removeprefix("node:")] = weight
    return label_weights


def shortlist_candidates(
    source: FunctionRecord,
    candidates: list[FunctionRecord],
    term_idf: Mapping[str, float],
    config: StructuralCloneConfig,
) -> list[tuple[FunctionRecord, float]]:
    """Return the top vector-similar candidates for one source function."""
    ranked: list[tuple[FunctionRecord, float]] = []
    for candidate in candidates:
        if is_same_record(source, candidate):
            continue
        if not stmt_ratio_ok(source, candidate, config.min_stmt_ratio):
            continue
        similarity = cosine_similarity(source["vector"], candidate["vector"], term_idf)
        if similarity < config.min_vector_similarity:
            continue
        ranked.append((clone_function_record(candidate), similarity))

    ranked.sort(
        key=lambda item: (
            -item[1],
            item[0]["path"],
            item[0]["lineno"],
            item[0]["qualname"],
        )
    )
    return ranked[: config.shortlist_size]


def is_same_record(left: FunctionRecord, right: FunctionRecord) -> bool:
    """Return True when two records refer to the same function."""
    return (
        left["path"] == right["path"]
        and left["qualname"] == right["qualname"]
        and left["lineno"] == right["lineno"]
    )


def stmt_ratio_ok(left: FunctionRecord, right: FunctionRecord, minimum_ratio: float) -> bool:
    """Check whether statement counts are close enough."""
    larger = max(left["stmt_count"], right["stmt_count"])
    smaller = min(left["stmt_count"], right["stmt_count"])
    if larger == 0:
        return False
    return (float(smaller) / float(larger)) >= minimum_ratio


def cosine_similarity(
    left: Mapping[str, float],
    right: Mapping[str, float],
    term_idf: Mapping[str, float],
) -> float:
    """Compute cosine similarity under IDF weighting."""
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0

    for term, value in left.items():
        weight = term_idf.get(term, 1.0)
        scaled = value * weight
        left_norm += scaled * scaled

    for term, value in right.items():
        weight = term_idf.get(term, 1.0)
        scaled = value * weight
        right_norm += scaled * scaled

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    shared_terms = set(left) & set(right)
    for term in shared_terms:
        weight = term_idf.get(term, 1.0)
        dot += left[term] * right[term] * weight * weight

    return dot / math.sqrt(left_norm * right_norm)


def anti_unification_similarity(
    left: NormalizedNode,
    right: NormalizedNode,
    label_weights: Mapping[str, float],
) -> float:
    """Compute anti-unification similarity from weighted substitution cost."""
    total_size = weighted_tree_size(left, label_weights) + weighted_tree_size(right, label_weights)
    if total_size == 0.0:
        return 0.0
    cost = weighted_substitution_cost(left, right, label_weights)
    similarity = 1.0 - (cost / total_size)
    return max(0.0, similarity)


def weighted_tree_size(node: NormalizedNode, label_weights: Mapping[str, float]) -> float:
    """Return weighted size of one normalized tree."""
    weight = label_weights.get(node["label"], 1.0)
    return weight + sum(weighted_tree_size(child, label_weights) for child in node["children"])


def _label_base_type(label: str) -> str:
    """Extract base AST type from a qualified label.

    ``"Call[foo]"`` → ``"Call"``, ``"BinOp[Add]"`` → ``"BinOp"``,
    ``"Name"`` → ``"Name"`` (unchanged for unqualified labels).
    """
    bracket = label.find("[")
    return label[:bracket] if bracket >= 0 else label


def weighted_substitution_cost(
    left: NormalizedNode,
    right: NormalizedNode,
    label_weights: Mapping[str, float],
) -> float:
    """Return the weighted placeholder cost between two trees.

    When children counts differ, LCS alignment matches shared structure
    before computing cost, so a single insertion does not cascade.

    When labels differ but share the same base AST type (e.g.
    ``Call[foo]`` vs ``Call[bar]``), a soft penalty is applied: only
    the label mismatch is penalised while children are still compared.
    """
    if left["label"] == right["label"]:
        return _children_cost(left["children"], right["children"], label_weights)

    if _label_base_type(left["label"]) == _label_base_type(right["label"]):
        label_cost = label_weights.get(left["label"], 1.0) + label_weights.get(right["label"], 1.0)
        return label_cost + _children_cost(left["children"], right["children"], label_weights)

    return weighted_tree_size(left, label_weights) + weighted_tree_size(right, label_weights)


def _children_cost(
    left_children: list[NormalizedNode],
    right_children: list[NormalizedNode],
    label_weights: Mapping[str, float],
) -> float:
    """Compare two child lists, using pairwise or LCS alignment."""
    if len(left_children) == len(right_children):
        return sum(
            weighted_substitution_cost(lc, rc, label_weights)
            for lc, rc in zip(left_children, right_children, strict=True)
        )

    aligned = _lcs_alignment(left_children, right_children)
    cost = 0.0
    for lc, rc in aligned:
        if lc is not None and rc is not None:
            cost += weighted_substitution_cost(lc, rc, label_weights)
        elif lc is not None:
            cost += weighted_tree_size(lc, label_weights)
        else:
            assert rc is not None
            cost += weighted_tree_size(rc, label_weights)
    return cost


def _lcs_alignment(
    left: list[NormalizedNode],
    right: list[NormalizedNode],
) -> list[tuple[NormalizedNode | None, NormalizedNode | None]]:
    """Align two child lists via LCS on node labels, returning matched and unmatched pairs."""
    n, m = len(left), len(right)
    dp: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if left[i]["label"] == right[j]["label"]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])

    result: list[tuple[NormalizedNode | None, NormalizedNode | None]] = []
    i, j = 0, 0
    while i < n and j < m:
        if left[i]["label"] == right[j]["label"]:
            result.append((left[i], right[j]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            result.append((left[i], None))
            i += 1
        else:
            result.append((None, right[j]))
            j += 1
    while i < n:
        result.append((left[i], None))
        i += 1
    while j < m:
        result.append((None, right[j]))
        j += 1
    return result


def relative_path(path: str, repo_root: Path) -> str:
    """Return a repo-relative path when possible."""
    try:
        return str(Path(path).resolve().relative_to(repo_root))
    except ValueError:
        return Path(path).name
