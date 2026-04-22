use serde_json::json;
use std::io::{self, Write};

use crate::input::HookInput;

fn config_dir() -> std::path::PathBuf {
    home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join("config")
}

fn read_config(filename: &str) -> String {
    std::fs::read_to_string(config_dir().join(filename))
        .unwrap_or_default()
        .trim()
        .to_string()
}

fn output(ctx: &str) {
    let msg =
        json!({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}});
    let _ = writeln!(io::stdout(), "{msg}");
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if !command.is_empty() {
        let re = regex::Regex::new(r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)git\s").unwrap();
        if re.is_match(command) {
            let rules = read_config("git.toml");
            if !rules.is_empty() {
                output(&rules);
            }
            return;
        }
    }

    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    let ext = std::path::Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    if ext.is_empty() {
        return;
    }

    let common = read_config("common.toml");
    let mut rules = read_config(&format!("{ext}.toml"));

    if ext == "md" {
        let mmd = read_config("mmd.toml");
        if !mmd.is_empty() {
            rules = if rules.is_empty() {
                mmd
            } else {
                format!("{rules}\n\n{mmd}")
            };
        }
    }

    if !common.is_empty() {
        rules = if rules.is_empty() {
            common
        } else {
            format!("{common}\n\n{rules}")
        };
    }

    if !rules.is_empty() {
        output(&rules);
    }
}
