"""Compare Python vs Rust structural-duplicate hooks on external benchmark repos.

This benchmark runs the existing hook entrypoints as subprocesses with identical
JSON payloads, so it measures end-to-end hook latency rather than just the core
matching logic.

By default:
- `public-apis` runs on all tracked Python files
- `youtube-dl` runs on an evenly spaced sample of 25 tracked Python files

Run:
  python3 tests/benchmarks/structural_clone_core/compare_python_rust_hooks.py
  python3 tests/benchmarks/structural_clone_core/compare_python_rust_hooks.py --repo youtube-dl --limit 50
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
HOOKS_DIR = ROOT_DIR / "hooks"
RUST_DIR = ROOT_DIR / "hooks-rs"
RUST_MANIFEST = RUST_DIR / "Cargo.toml"
RUST_BINARY = RUST_DIR / "target" / "release" / "claude-hooks"
CACHE_FILENAME = "structural-clone-index.json"


@dataclass(frozen=True)
class RepoSpec:
    name: str
    directory: Path
    default_limit: int | None


@dataclass(frozen=True)
class HookRunner:
    name: str
    command: tuple[str, ...]
    env_overrides: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FileRun:
    path: Path
    elapsed_ms: float
    stop: bool
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RunnerSummary:
    name: str
    file_count: int
    stop_count: int
    error_count: int
    total_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    max_ms: float


REPOS: dict[str, RepoSpec] = {
    "public-apis": RepoSpec(
        name="public-apis",
        directory=Path(__file__).resolve().parent / "public-apis",
        default_limit=None,
    ),
    "youtube-dl": RepoSpec(
        name="youtube-dl",
        directory=Path(__file__).resolve().parent / "youtube-dl",
        default_limit=25,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        choices=sorted(REPOS),
        help="Benchmark one repo. Repeatable. Defaults to all configured repos.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override the max file count per repo. Files are sampled evenly.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used for the Python hook runner.",
    )
    parser.add_argument(
        "--skip-rust-build",
        action="store_true",
        help="Skip `cargo build --release` and use the existing Rust binary.",
    )
    return parser.parse_args()


def ensure_rust_binary(skip_build: bool) -> None:
    if skip_build and not RUST_BINARY.is_file():
        raise SystemExit(f"Rust binary not found: {RUST_BINARY}")
    if skip_build:
        return
    subprocess.run(
        ["cargo", "build", "--quiet", "--release", "--manifest-path", str(RUST_MANIFEST)],
        cwd=ROOT_DIR,
        check=True,
    )


def runners(python_exe: str) -> list[HookRunner]:
    return [
        HookRunner(
            name="python",
            command=(python_exe, str(HOOKS_DIR / "warn-structural-duplicates.py")),
            env_overrides=(("PYTHONWARNINGS", "ignore::SyntaxWarning"),),
        ),
        HookRunner(
            name="rust",
            command=(str(RUST_BINARY), "warn-structural-duplicates"),
        ),
    ]


def tracked_python_files(repo_dir: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(repo_dir), "ls-files", "*.py"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return [(repo_dir / rel_path).resolve() for rel_path in proc.stdout.splitlines() if rel_path]


def evenly_sample(files: list[Path], limit: int | None) -> list[Path]:
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    if limit == 1:
        return [files[0]]

    last_index = len(files) - 1
    sampled: list[Path] = []
    seen: set[int] = set()
    for i in range(limit):
        index = round(i * last_index / (limit - 1))
        if index in seen:
            continue
        sampled.append(files[index])
        seen.add(index)
    return sampled


def clear_repo_cache(repo_dir: Path) -> None:
    cache_path = repo_dir / ".cache" / CACHE_FILENAME
    cache_path.unlink(missing_ok=True)


def run_hook(runner: HookRunner, file_path: Path) -> FileRun:
    payload = json.dumps({"tool_input": {"file_path": str(file_path)}})
    env = os.environ.copy()
    env.update(dict(runner.env_overrides))

    start = time.perf_counter()
    proc = subprocess.run(
        runner.command,
        input=payload,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    stdout = proc.stdout.strip()
    stop = False
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            stop = False
        else:
            stop = parsed.get("decision") == "stop"

    return FileRun(
        path=file_path,
        elapsed_ms=elapsed_ms,
        stop=stop,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=proc.stderr.strip(),
    )


def summarize(runner: HookRunner, runs: list[FileRun]) -> RunnerSummary:
    elapsed = sorted(run.elapsed_ms for run in runs)
    total_ms = sum(elapsed)
    p95_index = math.ceil(len(elapsed) * 0.95) - 1
    return RunnerSummary(
        name=runner.name,
        file_count=len(runs),
        stop_count=sum(1 for run in runs if run.stop),
        error_count=sum(1 for run in runs if run.returncode != 0),
        total_ms=total_ms,
        mean_ms=statistics.fmean(elapsed),
        median_ms=statistics.median(elapsed),
        p95_ms=elapsed[max(p95_index, 0)],
        max_ms=elapsed[-1],
    )


def relative_to_repo(path: Path, repo_dir: Path) -> str:
    return str(path.relative_to(repo_dir))


def benchmark_repo(spec: RepoSpec, selected_files: list[Path], runner: HookRunner) -> list[FileRun]:
    clear_repo_cache(spec.directory)
    print(f"[{spec.name}] {runner.name}: {len(selected_files)} files")
    runs: list[FileRun] = []
    for index, file_path in enumerate(selected_files, start=1):
        run = run_hook(runner, file_path)
        runs.append(run)
        if index == len(selected_files) or index % 5 == 0:
            print(f"  {index:>3}/{len(selected_files)} done")
    return runs


def mismatch_rows(
    spec: RepoSpec,
    python_runs: list[FileRun],
    rust_runs: list[FileRun],
) -> list[str]:
    rows: list[str] = []
    for py_run, rs_run in zip(python_runs, rust_runs, strict=True):
        if py_run.stop == rs_run.stop:
            continue
        rows.append(
            f"  - {relative_to_repo(py_run.path, spec.directory)}: "
            f"python={'stop' if py_run.stop else 'pass'}, "
            f"rust={'stop' if rs_run.stop else 'pass'}"
        )
    return rows


def print_summary(
    spec: RepoSpec,
    total_files: int,
    selected_files: list[Path],
    python_summary: RunnerSummary,
    rust_summary: RunnerSummary,
    python_runs: list[FileRun],
    rust_runs: list[FileRun],
) -> None:
    print()
    print(f"=== {spec.name} ===")
    print(f"Tracked Python files: {total_files}")
    if len(selected_files) == total_files:
        print(f"Benchmarked files:   {len(selected_files)} (all tracked files)")
    else:
        print(f"Benchmarked files:   {len(selected_files)} (evenly sampled)")
    print()

    header = (
        f"{'Runner':<8} {'Total(s)':>9} {'Mean(ms)':>10} {'Median':>10} "
        f"{'P95':>10} {'Max':>10} {'Stops':>7} {'Errors':>7}"
    )
    print(header)
    print("-" * len(header))
    for summary in (python_summary, rust_summary):
        print(
            f"{summary.name:<8} "
            f"{summary.total_ms / 1000:>9.2f} "
            f"{summary.mean_ms:>10.1f} "
            f"{summary.median_ms:>10.1f} "
            f"{summary.p95_ms:>10.1f} "
            f"{summary.max_ms:>10.1f} "
            f"{summary.stop_count:>7} "
            f"{summary.error_count:>7}"
        )

    if rust_summary.total_ms > 0:
        print(f"Speedup: python / rust = {python_summary.total_ms / rust_summary.total_ms:.2f}x")

    mismatches = mismatch_rows(spec, python_runs, rust_runs)
    print(f"Decision mismatches: {len(mismatches)}")
    if mismatches:
        print("First mismatches:")
        for row in mismatches[:10]:
            print(row)

    python_errors = [run for run in python_runs if run.returncode != 0]
    rust_errors = [run for run in rust_runs if run.returncode != 0]
    if python_errors or rust_errors:
        print("Error samples:")
        for run in [*python_errors[:3], *rust_errors[:3]]:
            print(
                f"  - {run.path}: returncode={run.returncode}, "
                f"stderr={run.stderr or '<empty>'}"
            )


def selected_repo_specs(args: argparse.Namespace) -> list[RepoSpec]:
    names = args.repo if args.repo else sorted(REPOS)
    return [REPOS[name] for name in names]


def main() -> None:
    args = parse_args()
    ensure_rust_binary(skip_build=args.skip_rust_build)
    hook_runners = runners(args.python)
    python_runner, rust_runner = hook_runners

    for spec in selected_repo_specs(args):
        files = tracked_python_files(spec.directory)
        limit = args.limit if args.limit is not None else spec.default_limit
        selected_files = evenly_sample(files, limit)

        python_runs = benchmark_repo(spec, selected_files, python_runner)
        rust_runs = benchmark_repo(spec, selected_files, rust_runner)

        python_summary = summarize(python_runner, python_runs)
        rust_summary = summarize(rust_runner, rust_runs)
        print_summary(
            spec=spec,
            total_files=len(files),
            selected_files=selected_files,
            python_summary=python_summary,
            rust_summary=rust_summary,
            python_runs=python_runs,
            rust_runs=rust_runs,
        )
        print()


if __name__ == "__main__":
    main()
