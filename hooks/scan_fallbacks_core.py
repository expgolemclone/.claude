#!/usr/bin/env python3
"""Detect fallback-style code paths in Python source files.

Reusable AST scanner — project-specific settings (scan roots, exclude dirs,
custom function names) are passed in as arguments or loaded from
``config/scan_fallbacks.toml`` by the calling hook / CLI.

Standalone usage::

    python3 scan_fallbacks_core.py /path/to/project [--pattern NAME] [--json] [--quiet]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tokenize
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_FALLBACK_FN_NAMES: frozenset[str] = frozenset(
    {"_prefer", "fallback", "coalesce", "_default"}
)
DEFAULT_FALLBACK_FN_PREFIXES: tuple[str, ...] = ("safe_", "_safe_")
_FALLBACK_LITERAL_VALUES: frozenset[object] = frozenset({0, 0.0, False, "", None})


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    col: int
    pattern: str
    snippet: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.col} [{self.pattern}] {self.snippet}"


# ------------------------------------------------------------------
# AST helpers
# ------------------------------------------------------------------

def is_none_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def is_fallback_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value in _FALLBACK_LITERAL_VALUES
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return not node.elts
    return isinstance(node, ast.Dict) and not node.keys


def is_none_check(test: ast.AST) -> bool:
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op = test.ops[0]
        if isinstance(op, (ast.Is, ast.IsNot)) and is_none_constant(test.comparators[0]):
            return True
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return isinstance(test.operand, ast.Name)
    return False


def handler_is_importerror(handler: ast.ExceptHandler) -> bool:
    exc = handler.type
    if exc is None:
        return True
    return isinstance(exc, ast.Name) and exc.id in {"ImportError", "ModuleNotFoundError"}


def handler_is_swallow(handler: ast.ExceptHandler) -> bool:
    body = handler.body
    if not body or any(isinstance(stmt, ast.Raise) for stmt in body):
        return False
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True
    last = body[-1]
    if isinstance(last, ast.Return) and (last.value is None or isinstance(last.value, ast.Constant)):
        return True
    return isinstance(last, ast.Assign)


def extract_callable_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def is_known_fallback_helper(
    name: str | None,
    *,
    fn_names: frozenset[str] = DEFAULT_FALLBACK_FN_NAMES,
    fn_prefixes: tuple[str, ...] = DEFAULT_FALLBACK_FN_PREFIXES,
) -> bool:
    if name is None:
        return False
    return name in fn_names or any(name.startswith(p) for p in fn_prefixes)


# ------------------------------------------------------------------
# Visitor
# ------------------------------------------------------------------

class FallbackVisitor(ast.NodeVisitor):
    def __init__(
        self,
        source_lines: list[str],
        rel_path: str,
        *,
        fn_names: frozenset[str] = DEFAULT_FALLBACK_FN_NAMES,
        fn_prefixes: tuple[str, ...] = DEFAULT_FALLBACK_FN_PREFIXES,
    ) -> None:
        self.findings: list[Finding] = []
        self._lines = source_lines
        self._rel = rel_path
        self._fn_names = fn_names
        self._fn_prefixes = fn_prefixes

    def _snippet(self, node: ast.expr | ast.stmt | ast.excepthandler) -> str:
        idx = node.lineno - 1
        return self._lines[idx].strip() if 0 <= idx < len(self._lines) else ""

    def _record(self, node: ast.expr | ast.stmt | ast.excepthandler, pattern: str) -> None:
        self.findings.append(
            Finding(self._rel, node.lineno, node.col_offset, pattern, self._snippet(node))
        )

    def visit_Try(self, node: ast.Try) -> None:
        body_is_imports = bool(node.body) and all(
            isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in node.body
        )
        for handler in node.handlers:
            if body_is_imports and handler_is_importerror(handler):
                self._record(handler, "import_fallback")
            if handler_is_swallow(handler):
                self._record(handler, "try_except_swallow")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or) and is_fallback_literal(node.values[-1]):
            self._record(node, "or_default")
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        if is_none_check(node.test):
            self._record(node, "ternary_none_else")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and len(node.args) == 2
            and not is_none_constant(node.args[1])
        ):
            self._record(node, "dict_get_default")
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) == 3:
            self._record(node, "getattr_default")
        if is_known_fallback_helper(
            extract_callable_name(func),
            fn_names=self._fn_names,
            fn_prefixes=self._fn_prefixes,
        ):
            self._record(node, "fallback_call")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if (
            is_none_check(node.test)
            and len(node.body) == 1
            and isinstance(node.body[0], (ast.Assign, ast.AugAssign))
        ):
            self._record(node, "if_none_assign")
        self.generic_visit(node)


# ------------------------------------------------------------------
# Comment scanning
# ------------------------------------------------------------------

def collect_fallback_comments(
    path: Path, source_lines: list[str], rel_path: str
) -> list[Finding]:
    findings: list[Finding] = []
    with path.open("rb") as fh:
        try:
            tokens = list(tokenize.tokenize(fh.readline))
        except tokenize.TokenError:
            return findings
    for tok in tokens:
        if tok.type != tokenize.COMMENT or "fallback" not in tok.string.lower():
            continue
        line_idx = tok.start[0] - 1
        snippet = source_lines[line_idx].strip() if 0 <= line_idx < len(source_lines) else ""
        findings.append(
            Finding(rel_path, tok.start[0], tok.start[1], "fallback_comment", snippet)
        )
    return findings


# ------------------------------------------------------------------
# File scanning
# ------------------------------------------------------------------

def scan_file(
    path: Path,
    *,
    rel_display: str | None = None,
    fn_names: frozenset[str] = DEFAULT_FALLBACK_FN_NAMES,
    fn_prefixes: tuple[str, ...] = DEFAULT_FALLBACK_FN_PREFIXES,
) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    rel = rel_display if rel_display is not None else str(path)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    lines = source.splitlines()
    visitor = FallbackVisitor(lines, rel, fn_names=fn_names, fn_prefixes=fn_prefixes)
    visitor.visit(tree)
    return visitor.findings + collect_fallback_comments(path, lines, rel)


def iter_python_files(
    project_root: Path,
    scan_roots: tuple[str, ...],
    exclude_dirs: frozenset[str],
) -> list[Path]:
    files: list[Path] = []
    for root in scan_roots:
        base = project_root / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in exclude_dirs for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


# ------------------------------------------------------------------
# Report formatting
# ------------------------------------------------------------------

def format_text_report(
    findings: list[Finding], file_count: int, scan_roots: tuple[str, ...]
) -> str:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.pattern, []).append(finding)
    out: list[str] = [
        "=" * 72,
        "  Fallback logic detection report",
        "=" * 72,
        f"Scanned {file_count} files under {', '.join(scan_roots)}/",
        f"Found {len(findings)} occurrences across {len(grouped)} pattern categories:",
        "",
    ]
    for pattern in sorted(grouped):
        items = sorted(grouped[pattern], key=lambda f: (f.file, f.line))
        out.append(f"## {pattern} ({len(items)})")
        out.extend(f"  {f.file}:{f.line}:{f.col}  {f.snippet}" for f in items)
        out.append("")
    out.append(f"Total: {len(findings)} findings")
    return "\n".join(out)


def format_json_report(findings: list[Finding]) -> str:
    return json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# TOML config loading
# ------------------------------------------------------------------

def load_toml_config(project_root: Path) -> dict[str, object]:
    path = project_root / "config" / "scan_fallbacks.toml"
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def config_to_params(
    cfg: dict[str, object],
) -> tuple[tuple[str, ...], frozenset[str], frozenset[str], tuple[str, ...]]:
    """Extract scanner parameters from parsed TOML.

    Returns (scan_roots, exclude_dirs, fn_names, fn_prefixes).
    """
    raw_section = cfg.get("scan_fallbacks")
    section: dict[str, object] = raw_section if isinstance(raw_section, dict) else {}

    raw_roots = section.get("scan_roots")
    scan_roots: tuple[str, ...] = tuple(raw_roots) if isinstance(raw_roots, list) else ()

    raw_exclude = section.get("exclude_dirs")
    exclude_dirs: frozenset[str] = frozenset(raw_exclude) if isinstance(raw_exclude, list) else frozenset()

    raw_funcs = section.get("functions")
    funcs: dict[str, object] = raw_funcs if isinstance(raw_funcs, dict) else {}

    raw_names = funcs.get("names")
    fn_names: frozenset[str] = frozenset(raw_names) if isinstance(raw_names, list) else DEFAULT_FALLBACK_FN_NAMES

    raw_prefixes = funcs.get("prefixes")
    fn_prefixes: tuple[str, ...] = tuple(raw_prefixes) if isinstance(raw_prefixes, list) else DEFAULT_FALLBACK_FN_PREFIXES

    return scan_roots, exclude_dirs, fn_names, fn_prefixes


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan project for fallback patterns")
    parser.add_argument(
        "project_root", nargs="?", default=".",
        help="Project root directory (default: cwd)",
    )
    parser.add_argument("--pattern", help="Filter output to a single pattern name")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output; use exit code only"
    )
    parser.add_argument(
        "--allow-findings",
        action="store_true",
        help="Return 0 even when findings exist (inventory mode)",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    cfg = load_toml_config(project_root)
    if not cfg:
        print(f"No config/scan_fallbacks.toml in {project_root}", file=sys.stderr)
        return 1
    scan_roots, exclude_dirs, fn_names, fn_prefixes = config_to_params(cfg)

    files = iter_python_files(project_root, scan_roots, exclude_dirs)
    findings: list[Finding] = []
    for path in files:
        rel = str(path.relative_to(project_root))
        findings.extend(
            scan_file(path, rel_display=rel, fn_names=fn_names, fn_prefixes=fn_prefixes)
        )
    if args.pattern:
        findings = [f for f in findings if f.pattern == args.pattern]

    if not args.quiet:
        if args.json:
            print(format_json_report(findings))
        else:
            print(format_text_report(findings, len(files), scan_roots))

    return 0 if (args.allow_findings or not findings) else 1


if __name__ == "__main__":
    sys.exit(main())
