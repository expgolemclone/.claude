use serde_json::json;
use std::io::{self, Write};
use std::time::Duration;

use crate::input::HookInput;
use crate::process::{CommandError, output_with_timeout};

const PATCH_NOTIFY_MARKER: &str = "パッチ適用";

fn update_message(stdout: &str, stderr: &str, success: bool) -> Option<String> {
    if success {
        let output = stdout.trim();
        if output.is_empty() {
            None
        } else {
            Some(format!("[update] {output}"))
        }
    } else {
        Some(format!("[update] update failed: {}", stderr.trim()))
    }
}

fn patch_message(stdout: &str) -> Option<String> {
    let output = stdout.trim();
    if output.contains(PATCH_NOTIFY_MARKER) {
        Some(format!("[patch] {output}"))
    } else {
        None
    }
}

pub fn run(input: &HookInput) {
    if input.permission_mode == "plan" {
        return;
    }

    let mut messages: Vec<String> = Vec::new();

    let mut update_cmd = std::process::Command::new("npm");
    update_cmd.args(["install", "-g", "@anthropic-ai/claude-code@latest"]);
    match output_with_timeout(&mut update_cmd, Duration::from_secs(90)) {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            if let Some(message) = update_message(&stdout, &stderr, output.status.success()) {
                messages.push(message);
            }
        }
        Err(CommandError::TimedOut) => {
            messages.push("[update] update failed: timed out after 90s".to_string());
        }
        Err(CommandError::Io(err)) => {
            messages.push(format!("[update] update failed: {err}"));
        }
    }

    let current_exe = match std::env::current_exe() {
        Ok(path) => path,
        Err(_) => return,
    };
    let mut patch_cmd = std::process::Command::new(current_exe);
    patch_cmd.arg("patch-clawd-mascot");
    match output_with_timeout(&mut patch_cmd, Duration::from_secs(120)) {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            if let Some(message) = patch_message(&stdout) {
                messages.push(message);
            }
        }
        Err(CommandError::TimedOut | CommandError::Io(_)) => {}
    }

    if !messages.is_empty() {
        let msg = json!({"systemMessage": messages.join("\n")});
        let _ = writeln!(io::stdout(), "{msg}");
    }
}

#[cfg(test)]
mod tests {
    use super::{patch_message, update_message};

    #[test]
    fn update_failures_are_reported() {
        assert_eq!(
            update_message("", "permission denied", false),
            Some("[update] update failed: permission denied".to_string())
        );
    }

    #[test]
    fn patch_message_requires_notify_marker() {
        assert_eq!(
            patch_message("パッチ適用: mascot hidden"),
            Some("[patch] パッチ適用: mascot hidden".to_string())
        );
        assert_eq!(patch_message("already patched"), None);
    }
}
