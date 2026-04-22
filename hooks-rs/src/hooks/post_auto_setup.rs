use regex::Regex;
use serde_json::json;
use std::io::{self, Write};

use crate::input::HookInput;

pub fn run(input: &HookInput) {
    let cwd = &input.cwd;
    let command = &input.tool_input.command;
    if command.is_empty() || cwd.is_empty() {
        return;
    }

    if !Regex::new(r"\bgit\s+(pull|commit)\b")
        .unwrap()
        .is_match(command)
    {
        return;
    }
    let normalized = cwd.replace('\\', "/").trim_end_matches('/').to_string();
    if !normalized.ends_with("/.claude") {
        return;
    }

    let output = std::process::Command::new("uv")
        .args(["run", "python", "setup.py"])
        .current_dir(cwd)
        .output();

    let output = match output {
        Ok(o) => o,
        Err(_) => return,
    };

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let text = if !stdout.is_empty() { stdout } else { stderr };
    if !text.is_empty() {
        let msg = json!({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": format!("[auto] setup.py executed:\n{text}")}});
        let _ = writeln!(io::stdout(), "{msg}");
    }
}
