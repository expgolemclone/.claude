use regex::Regex;

use crate::input::HookInput;
use crate::nix_protected::{check_config_diff, check_mkforce_override};
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if !Regex::new(r"\bgit\s+commit\b").unwrap().is_match(command) {
        return;
    }

    let nix_config = home::home_dir().unwrap_or_default().join("nix-config");
    let output = std::process::Command::new("git")
        .args(["diff", "--cached"])
        .current_dir(&nix_config)
        .output();

    let diff_text = match output {
        Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).to_string(),
        _ => return,
    };

    if diff_text.trim().is_empty() {
        return;
    }

    if let Some(reason) = check_config_diff(&diff_text) {
        block(&reason);
        return;
    }
    if let Some(reason) = check_mkforce_override(&diff_text) {
        block(&reason);
        return;
    }
    pass();
}
