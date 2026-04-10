"""E2E benchmark for the structural clone detection hook."""

import importlib
import io
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("warn-structural-duplicates")
main = mod.main


def generate_function(name: str, body_lines: int, variant: int = 0) -> str:
    """Generate a synthetic Python function with configurable size."""
    lines = [f"def {name}(arg_{variant}: object) -> None:"]
    for i in range(body_lines):
        lines.append(f"    val_{i} = process(arg_{variant}, step={i + variant})")
    lines.append(f"    return finalize(val_{body_lines - 1})")
    return "\n".join(lines) + "\n\n"


def setup_repo(tmp: Path, *, num_files: int, funcs_per_file: int, body_lines: int) -> Path:
    """Create a git repo with synthetic Python files."""
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "bench"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "b@b"], cwd=tmp, check=True, capture_output=True)

    for file_idx in range(num_files):
        content = ""
        for func_idx in range(funcs_per_file):
            content += generate_function(
                f"func_{file_idx}_{func_idx}",
                body_lines,
                variant=func_idx,
            )
        (tmp / f"mod_{file_idx}.py").write_text(content, encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp, check=True, capture_output=True,
    )

    target = tmp / "target.py"
    content = ""
    for i in range(funcs_per_file):
        content += generate_function(f"target_func_{i}", body_lines, variant=i)
    target.write_text(content, encoding="utf-8")
    return target


def run_hook(file_path: str) -> str:
    from unittest import mock

    payload = {"tool_input": {"file_path": file_path}}
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        return out.getvalue()


def bench(label: str, target: Path, iterations: int) -> None:
    """Run the hook multiple times and report statistics."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        run_hook(str(target))
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    print(f"\n--- {label} ({iterations} iterations) ---")
    print(f"  mean:   {statistics.mean(times) * 1000:8.1f} ms")
    print(f"  median: {statistics.median(times) * 1000:8.1f} ms")
    print(f"  min:    {min(times) * 1000:8.1f} ms")
    print(f"  max:    {max(times) * 1000:8.1f} ms")
    if len(times) > 1:
        print(f"  stdev:  {statistics.stdev(times) * 1000:8.1f} ms")


def main_bench() -> None:
    import shutil
    import tempfile

    scenarios = [
        {"label": "small  (10 files x 5 funcs)", "num_files": 10, "funcs_per_file": 5, "body_lines": 6},
        {"label": "medium (30 files x 10 funcs)", "num_files": 30, "funcs_per_file": 10, "body_lines": 8},
        {"label": "large  (80 files x 15 funcs)", "num_files": 80, "funcs_per_file": 15, "body_lines": 10},
    ]
    iterations = 5

    for scenario in scenarios:
        tmp = Path(tempfile.mkdtemp())
        try:
            target = setup_repo(
                tmp,
                num_files=scenario["num_files"],
                funcs_per_file=scenario["funcs_per_file"],
                body_lines=scenario["body_lines"],
            )

            # cold run (no cache)
            cache_dir = tmp / ".cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            bench(f"{scenario['label']} [cold]", target, iterations=1)

            # warm runs (with cache)
            bench(f"{scenario['label']} [warm]", target, iterations=iterations)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_bench()
