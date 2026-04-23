#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write): run oxisym via Dylint to detect structural duplicates in Rust code."""

import json
import os
import subprocess
import sys

from project_root import find_project_root

OXISYM_LIB_DIR = "/home/exp/.claude/external/oxisym/target/release"
DYLINT_BIN_DIR = "/home/exp/.claude/external/dylint/target/release"
NIX_SHELL = "/home/exp/.claude/external/nightly-rust-combined.nix"
FAKE_RUSTUP_DIR = "/tmp"
FAKE_RUSTUP_HOME = "/tmp/fake-rustup-home"
FAKE_CARGO_HOME = "/tmp/fake-cargo-home"
TOOLCHAIN = "nightly-2025-09-18-x86_64-unknown-linux-gnu"
OPENSSL_LIB = "/nix/store/bga5xf95jaypy385hvxm4h3yxl3m1566-openssl-3.6.1/lib"
FENIX_SYSROOT = "/nix/store/gx7i7dg4c0s8g4ycsh0q7bj2w3x9sl2g-rust-mixed"


def ensure_fake_rustup() -> None:
    """Create fake rustup wrapper and sysroot symlink if missing."""
    rustup_path = os.path.join(FAKE_RUSTUP_DIR, "rustup")
    if not os.path.exists(rustup_path):
        with open(rustup_path, "w") as f:
            f.write(f"""#!/bin/sh
case "$1" in
    which)
        case "$2" in
            rustc) echo "{FENIX_SYSROOT}/bin/rustc" ;;
            cargo) echo "{FENIX_SYSROOT}/bin/cargo" ;;
            *) echo "{FENIX_SYSROOT}/bin/rustc" ;;
        esac
        ;;
    show)
        echo "{TOOLCHAIN} (default)"
        ;;
    run)
        shift 2
        exec "$@"
        ;;
    *)
        echo "rustup-compatible wrapper for NixOS" >&2
        ;;
esac
""")
        os.chmod(rustup_path, 0o755)

    toolchain_dir = os.path.join(FAKE_RUSTUP_HOME, "toolchains")
    symlink = os.path.join(toolchain_dir, TOOLCHAIN)
    if not os.path.exists(symlink):
        os.makedirs(toolchain_dir, exist_ok=True)
        os.symlink(FENIX_SYSROOT, symlink)


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

    if not file_path or not file_path.endswith(".rs"):
        return

    project_root = find_project_root(os.path.dirname(file_path))
    if not project_root:
        return

    ensure_fake_rustup()

    dylint_cmd = (
        f"export PATH={FAKE_RUSTUP_DIR}:{DYLINT_BIN_DIR}:$PATH && "
        f"export LD_LIBRARY_PATH={OPENSSL_LIB}:$LD_LIBRARY_PATH && "
        f"export RUSTUP_TOOLCHAIN={TOOLCHAIN} && "
        f"export RUSTUP_HOME={FAKE_RUSTUP_HOME} && "
        f"export CARGO_HOME={FAKE_CARGO_HOME} && "
        f"export DYLINT_LIBRARY_PATH={OXISYM_LIB_DIR} && "
        f"cargo dylint --lib oxisym 2>&1"
    )

    try:
        result = subprocess.run(
            ["nix-shell", NIX_SHELL, "--run", dylint_cmd],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return

    output = result.stdout.strip()
    if not output:
        return

    warnings = [
        line for line in output.splitlines()
        if any(k in line for k in ("structural similarity", "same body structure", "same function"))
        or line.strip().startswith("= help:")
    ]

    if not warnings:
        return

    listing = "\n".join(f"  - {w.strip()}" for w in warnings)
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"oxisym が構造的複製を検出しました。\n{listing}\n"
                    "共通化または抽象化を検討してください。"
                ),
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
