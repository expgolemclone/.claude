use serde_json::json;
use std::io::{self, Write};

use crate::input::HookInput;

pub fn run(input: &HookInput) {
    if input.permission_mode == "plan" {
        return;
    }

    let mut messages: Vec<String> = Vec::new();

    let update_msg = std::process::Command::new("npm")
        .args(["install", "-g", "@anthropic-ai/claude-code@latest"])
        .output();
    if let Ok(o) = update_msg {
        let stdout = String::from_utf8_lossy(&o.stdout).trim().to_string();
        if !stdout.is_empty() {
            messages.push(format!("[update] {stdout}"));
        }
    }

    let patch_script = home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join("scripts")
        .join("patch-clawd-mascot.py");
    let patch_msg = std::process::Command::new("python3")
        .arg(&patch_script)
        .output();
    if let Ok(o) = patch_msg {
        let stdout = String::from_utf8_lossy(&o.stdout).trim().to_string();
        if stdout.contains("\u{30d1}\u{30c3}\u{30c1}\u{9069}\u{7528}") {
            messages.push(format!("[patch] {stdout}"));
        }
    }

    if !messages.is_empty() {
        let msg = json!({"systemMessage": messages.join("\n")});
        let _ = writeln!(io::stdout(), "{msg}");
    }
}
