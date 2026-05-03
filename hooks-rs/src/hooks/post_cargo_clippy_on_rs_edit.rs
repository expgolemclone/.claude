use serde_json::json;
use std::io::{self, Write};
use std::path::Path;
use std::time::Duration;

use crate::input::HookInput;
use crate::process::output_with_timeout;
use crate::project_root::find_project_root;

const NIX_SHELL: &str = "/home/exp/.claude/external/nightly-rust-combined.nix";

fn clippy_context(diagnostics: &str) -> Option<String> {
    let diagnostics = diagnostics.trim();
    if diagnostics.is_empty() {
        None
    } else {
        Some(format!(
            "cargo clippy diagnostics:\n{diagnostics}\nFix these issues."
        ))
    }
}

fn ensure_fake_rustup() {
    let fake_rustup_dir = "/tmp";
    let fake_rustup_home = "/tmp/fake-rustup-home";
    let toolchain = "nightly-2025-09-18-x86_64-unknown-linux-gnu";
    let fenix_sysroot = "/nix/store/gx7i7dg4c0s8g4ycsh0q7bj2w3x9sl2g-rust-mixed";

    let rustup_path = format!("{fake_rustup_dir}/rustup");
    if !Path::new(&rustup_path).exists() {
        let script = format!(
            "#!/bin/sh\ncase \"$1\" in\n  which) case \"$2\" in \
             rustc) echo \"{fenix_sysroot}/bin/rustc\" ;; \
             cargo) echo \"{fenix_sysroot}/bin/cargo\" ;; \
             *) echo \"{fenix_sysroot}/bin/rustc\" ;; esac ;;\n  \
             show) echo \"{toolchain} (default)\" ;;\n  \
             run) shift 2; exec \"$@\" ;;\n  \
             *) echo \"rustup-compatible wrapper for NixOS\" >&2 ;;\nesac\n"
        );
        let _ = std::fs::write(&rustup_path, script);
        let _ = std::process::Command::new("chmod")
            .args(["+x", &rustup_path])
            .status();
    }

    let toolchain_dir = format!("{fake_rustup_home}/toolchains");
    let symlink = format!("{toolchain_dir}/{toolchain}");
    if !Path::new(&symlink).exists() {
        let _ = std::fs::create_dir_all(&toolchain_dir);
        let _ = std::os::unix::fs::symlink(fenix_sysroot, &symlink);
    }
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() || !file_path.ends_with(".rs") {
        return;
    }

    let dir = std::path::Path::new(file_path)
        .parent()
        .unwrap_or(std::path::Path::new("."));
    let project_root = match find_project_root(dir, "Cargo.toml") {
        Some(r) => r,
        None => return,
    };

    ensure_fake_rustup();

    let inner_cmd = "cargo clippy --color=never --quiet 2>&1";

    let mut command = std::process::Command::new("nix-shell");
    command
        .args([NIX_SHELL, "--run", inner_cmd])
        .current_dir(&project_root);

    let output = match output_with_timeout(&mut command, Duration::from_secs(120)) {
        Ok(o) => o,
        Err(_) => return,
    };

    let diagnostics = String::from_utf8_lossy(&output.stdout).to_string();
    let Some(context) = clippy_context(&diagnostics) else {
        return;
    };

    let msg = json!({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}});
    let _ = writeln!(io::stdout(), "{msg}");
}

#[cfg(test)]
mod tests {
    use super::clippy_context;

    #[test]
    fn builds_context_for_diagnostics() {
        let context = clippy_context("warning: unused variable").unwrap();
        assert!(context.contains("unused variable"));
    }

    #[test]
    fn returns_none_for_empty_diagnostics() {
        assert_eq!(clippy_context(""), None);
        assert_eq!(clippy_context("   \n"), None);
    }
}
