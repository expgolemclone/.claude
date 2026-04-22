use regex::Regex;

use crate::input::HookInput;
use crate::nix_protected::PROTECTED_PATTERNS;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with("configuration.nix") {
        return;
    }

    let compiled: Vec<Regex> = PROTECTED_PATTERNS
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect();

    match input.tool_name.as_str() {
        "Edit" => check_edit(input, &compiled),
        "Write" => check_write(input, &compiled),
        _ => pass(),
    }
}

fn check_edit(input: &HookInput, patterns: &[Regex]) {
    let old_string = &input.tool_input.old_string;
    let new_string = &input.tool_input.new_string;

    let old_matches: Vec<usize> = patterns
        .iter()
        .enumerate()
        .filter(|(_, re)| re.is_match(old_string))
        .map(|(i, _)| i)
        .collect();

    if old_matches.is_empty() {
        return;
    }

    for &idx in &old_matches {
        let old_lines: Vec<&str> = old_string
            .lines()
            .filter(|l| patterns[idx].is_match(l))
            .collect();
        let new_lines: Vec<&str> = new_string
            .lines()
            .filter(|l| patterns[idx].is_match(l))
            .collect();
        if old_lines != new_lines {
            block(&format!(
                "保護対象の設定行を変更しようとしています: {}",
                PROTECTED_PATTERNS[idx]
            ));
            return;
        }
    }
}

fn check_write(input: &HookInput, patterns: &[Regex]) {
    let path = std::path::Path::new(input.tool_input.file_path_resolved());
    if !path.exists() {
        return;
    }
    let current = std::fs::read_to_string(path).unwrap_or_default();
    let new_content = &input.tool_input.content;

    for (idx, re) in patterns.iter().enumerate() {
        let current_lines: Vec<&str> = current
            .lines()
            .filter(|l| re.is_match(l))
            .map(|l| l.trim())
            .collect();
        let new_lines: Vec<&str> = new_content
            .lines()
            .filter(|l| re.is_match(l))
            .map(|l| l.trim())
            .collect();
        if !current_lines.is_empty() && current_lines != new_lines {
            block(&format!(
                "保護対象の設定行が変更または削除されます: {}",
                PROTECTED_PATTERNS[idx]
            ));
            return;
        }
    }
}
