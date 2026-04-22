use regex::Regex;

use crate::input::HookInput;
use crate::nix_protected::{check_config_diff, check_mkforce_override};
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if !Regex::new(r"\bnixos-rebuild\b").unwrap().is_match(command) {
        return;
    }

    let nix_config = home::home_dir().unwrap_or_default().join("nix-config");
    let mut parts = Vec::new();
    for extra in [&[][..], &["--cached".to_string()]] {
        let mut args = vec!["diff".to_string()];
        args.extend(extra.iter().cloned());
        let output = std::process::Command::new("git")
            .args(&args)
            .current_dir(&nix_config)
            .output();
        if let Ok(o) = output
            && o.status.success()
        {
            parts.push(String::from_utf8_lossy(&o.stdout).to_string());
        }
    }

    let diff_text = parts.join("\n");
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
