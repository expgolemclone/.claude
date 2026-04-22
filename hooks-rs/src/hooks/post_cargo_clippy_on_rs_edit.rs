use serde_json::json;
use std::io::{self, Write};
use std::time::Duration;

use crate::input::HookInput;
use crate::process::output_with_timeout;
use crate::project_root::find_project_root;

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

    let mut command = std::process::Command::new("cargo");
    command
        .args(["clippy", "--color=never", "--quiet"])
        .current_dir(&project_root);

    let output = match output_with_timeout(&mut command, Duration::from_secs(120)) {
        Ok(o) => o,
        Err(_) => return,
    };

    let diagnostics = String::from_utf8_lossy(&output.stderr).to_string();
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
