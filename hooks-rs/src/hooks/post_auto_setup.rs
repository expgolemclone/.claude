use regex::Regex;
use serde_json::json;
use std::io::{self, Write};
use std::time::Duration;

use crate::input::HookInput;
use crate::process::output_with_timeout;

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

    let current_exe = match std::env::current_exe() {
        Ok(path) => path,
        Err(_) => return,
    };

    let mut command = std::process::Command::new(current_exe);
    command.arg("setup").current_dir(cwd);

    let output = match output_with_timeout(&mut command, Duration::from_secs(30)) {
        Ok(o) => o,
        Err(_) => return,
    };

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let text = if !stdout.is_empty() { stdout } else { stderr };
    if !text.is_empty() {
        let msg = json!({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": format!("[auto] claude-hooks setup executed:\n{text}")}});
        let _ = writeln!(io::stdout(), "{msg}");
    }
}
