use std::path::Path;
use std::process::Command;

use crate::input::HookInput;
use crate::output::stop;
use crate::project_root::find_project_root;

const OXISYM_LIB_DIR: &str = "/home/exp/.claude/external/oxisym/target/release";
const DYLINT_BIN_DIR: &str = "/home/exp/.claude/external/dylint/target/release";
const NIX_SHELL: &str = "/home/exp/.claude/external/nightly-rust-combined.nix";
const TOOLCHAIN: &str = "nightly-2025-09-18-x86_64-unknown-linux-gnu";
const OPENSSL_LIB: &str = "/nix/store/bga5xf95jaypy385hvxm4h3yxl3m1566-openssl-3.6.1/lib";
const FENIX_SYSROOT: &str = "/nix/store/gx7i7dg4c0s8g4ycsh0q7bj2w3x9sl2g-rust-mixed";
const FAKE_RUSTUP_DIR: &str = "/tmp";
const FAKE_RUSTUP_HOME: &str = "/tmp/fake-rustup-home";
const FAKE_CARGO_HOME: &str = "/tmp/fake-cargo-home";

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with(".rs") {
        return;
    }

    let path = Path::new(file_path);
    if !path.is_file() {
        return;
    }

    let project_root = match find_project_root(path, "Cargo.toml") {
        Some(root) => root,
        None => return,
    };

    ensure_fake_rustup();

    let output = match run_oxisym(&project_root) {
        Ok(out) => out,
        Err(_) => return,
    };

    let warnings = parse_warnings(&output);
    if warnings.is_empty() {
        return;
    }

    let listing = warnings
        .iter()
        .map(|w| format!("  - {w}"))
        .collect::<Vec<_>>()
        .join("\n");
    stop(&format!(
        "oxisym が構造的複製を検出しました。\n{listing}\n共通化または抽象化を検討してください。"
    ));
}

fn ensure_fake_rustup() {
    let rustup_path = format!("{FAKE_RUSTUP_DIR}/rustup");
    if !Path::new(&rustup_path).exists() {
        let script = format!(
            "#!/bin/sh\ncase \"$1\" in\n  which) case \"$2\" in \
             rustc) echo \"{FENIX_SYSROOT}/bin/rustc\" ;; \
             cargo) echo \"{FENIX_SYSROOT}/bin/cargo\" ;; \
             *) echo \"{FENIX_SYSROOT}/bin/rustc\" ;; esac ;;\n  \
             show) echo \"{TOOLCHAIN} (default)\" ;;\n  \
             run) shift 2; exec \"$@\" ;;\n  \
             *) echo \"rustup-compatible wrapper for NixOS\" >&2 ;;\nesac\n"
        );
        let _ = std::fs::write(&rustup_path, script);
        let _ = std::process::Command::new("chmod")
            .args(["+x", &rustup_path])
            .status();
    }

    let toolchain_dir = format!("{FAKE_RUSTUP_HOME}/toolchains");
    let symlink = format!("{toolchain_dir}/{TOOLCHAIN}");
    if !Path::new(&symlink).exists() {
        let _ = std::fs::create_dir_all(&toolchain_dir);
        let _ = std::os::unix::fs::symlink(FENIX_SYSROOT, &symlink);
    }
}

fn run_oxisym(project_root: &Path) -> Result<String, String> {
    let inner_cmd = format!(
        "export PATH={FAKE_RUSTUP_DIR}:{DYLINT_BIN_DIR}:$PATH && \
         export LD_LIBRARY_PATH={OPENSSL_LIB}:$LD_LIBRARY_PATH && \
         export RUSTUP_TOOLCHAIN={TOOLCHAIN} && \
         export RUSTUP_HOME={FAKE_RUSTUP_HOME} && \
         export CARGO_HOME={FAKE_CARGO_HOME} && \
         export DYLINT_LIBRARY_PATH={OXISYM_LIB_DIR} && \
         cargo dylint --lib oxisym 2>&1"
    );

    let output = Command::new("nix-shell")
        .args([NIX_SHELL, "--run", &inner_cmd])
        .current_dir(project_root)
        .output()
        .map_err(|e| e.to_string())?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    Ok(format!("{stdout}\n{stderr}"))
}

fn parse_warnings(output: &str) -> Vec<String> {
    let mut warnings = Vec::new();
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.contains("structural similarity")
            || trimmed.contains("same body structure")
            || trimmed.contains("same function")
        {
            warnings.push(trimmed.to_string());
        }
        if trimmed.starts_with("= help:") {
            warnings.push(trimmed.to_string());
        }
    }
    warnings
}
