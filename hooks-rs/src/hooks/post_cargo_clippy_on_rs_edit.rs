use serde_json::json;
use std::io::{self, Write};

use crate::input::HookInput;
use crate::project_root::find_project_root;

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

    let output = match std::process::Command::new("cargo")
        .args(["clippy", "--color=never", "--quiet"])
        .current_dir(&project_root)
        .output()
    {
        Ok(o) => o,
        Err(_) => return,
    };

    let diagnostics = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if diagnostics.is_empty() {
        return;
    }

    let msg = json!({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": format!("cargo clippy diagnostics:\n{diagnostics}\nFix these issues.")}});
    let _ = writeln!(io::stdout(), "{msg}");
}
