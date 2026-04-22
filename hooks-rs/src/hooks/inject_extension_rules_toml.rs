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

fn is_git_command(command: &str) -> bool {
    regex::Regex::new(r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)git\s")
        .unwrap()
        .is_match(command)
}

fn compose_rules(ext: &str, common: &str, specific: &str, mmd: &str) -> String {
    if ext.is_empty() {
        return String::new();
    }

    let mut rules = specific.trim().to_string();
    if ext == "md" && !mmd.trim().is_empty() {
        rules = if rules.is_empty() {
            mmd.trim().to_string()
        } else {
            format!("{}\n\n{}", rules, mmd.trim())
        };
    }

    if !common.trim().is_empty() {
        rules = if rules.is_empty() {
            common.trim().to_string()
        } else {
            format!("{}\n\n{}", common.trim(), rules)
        };
    }

    rules
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if !command.is_empty()
        && is_git_command(command) {
            let rules = read_config("git.toml");
            if !rules.is_empty() {
                output(&rules);
            }
            return;
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
    let specific = read_config(&format!("{ext}.toml"));
    let mmd = if ext == "md" {
        read_config("mmd.toml")
    } else {
        String::new()
    };
    let rules = compose_rules(&ext, &common, &specific, &mmd);

    if !rules.is_empty() {
        output(&rules);
    }
}

#[cfg(test)]
mod tests {
    use super::{compose_rules, is_git_command};

    #[test]
    fn detects_git_commit_command() {
        assert!(is_git_command("git commit -m 'test'"));
    }

    #[test]
    fn detects_git_command_after_separator() {
        assert!(is_git_command("cd repo && git push origin main"));
    }

    #[test]
    fn ignores_non_git_command() {
        assert!(!is_git_command("echo hello"));
    }

    #[test]
    fn composes_common_and_specific_rules() {
        assert_eq!(
            compose_rules("py", "common", "python", ""),
            "common\n\npython"
        );
    }

    #[test]
    fn markdown_includes_mmd_rules() {
        assert_eq!(
            compose_rules("md", "common", "markdown", "mindmap"),
            "common\n\nmarkdown\n\nmindmap"
        );
    }

    #[test]
    fn unknown_extension_gets_common_only() {
        assert_eq!(compose_rules("xyz", "common", "", ""), "common");
    }
}
