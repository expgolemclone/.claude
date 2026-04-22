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
        "Edit" => {
            if let Some(reason) = check_edit(input, &compiled) {
                block(&reason);
            }
        }
        "Write" => {
            if let Some(reason) = check_write(input, &compiled) {
                block(&reason);
            }
        }
        _ => pass(),
    }
}

fn check_edit(input: &HookInput, patterns: &[Regex]) -> Option<String> {
    let old_string = &input.tool_input.old_string;
    let new_string = &input.tool_input.new_string;

    let old_matches: Vec<usize> = patterns
        .iter()
        .enumerate()
        .filter(|(_, re)| re.is_match(old_string))
        .map(|(i, _)| i)
        .collect();

    if old_matches.is_empty() {
        return None;
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
            return Some(format!(
                "保護対象の設定行を変更しようとしています: {}",
                PROTECTED_PATTERNS[idx]
            ));
        }
    }

    None
}

fn check_write(input: &HookInput, patterns: &[Regex]) -> Option<String> {
    let path = std::path::Path::new(input.tool_input.file_path_resolved());
    if !path.exists() {
        return None;
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
            return Some(format!(
                "保護対象の設定行が変更または削除されます: {}",
                PROTECTED_PATTERNS[idx]
            ));
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::{check_edit, check_write};
    use crate::input::{HookInput, ToolInput};
    use regex::Regex;
    use tempfile::tempdir;

    fn compiled_patterns() -> Vec<Regex> {
        crate::nix_protected::PROTECTED_PATTERNS
            .iter()
            .map(|p| Regex::new(p).unwrap())
            .collect()
    }

    #[test]
    fn edit_detects_sysusers_change() {
        let input = HookInput {
            tool_name: "Edit".to_string(),
            tool_input: ToolInput {
                file_path: "hosts/nixos/configuration.nix".to_string(),
                old_string: "  systemd.sysusers.enable = false;".to_string(),
                new_string: "  systemd.sysusers.enable = true;".to_string(),
                ..Default::default()
            },
            ..Default::default()
        };
        let reason = check_edit(&input, &compiled_patterns()).unwrap();
        assert!(reason.contains("sysusers"));
    }

    #[test]
    fn edit_allows_non_protected_line_change() {
        let input = HookInput {
            tool_name: "Edit".to_string(),
            tool_input: ToolInput {
                file_path: "hosts/nixos/configuration.nix".to_string(),
                old_string: "    shell = pkgs.zsh;".to_string(),
                new_string: "    shell = pkgs.bash;".to_string(),
                ..Default::default()
            },
            ..Default::default()
        };
        assert_eq!(check_edit(&input, &compiled_patterns()), None);
    }

    #[test]
    fn write_detects_protected_line_removed() {
        let dir = tempdir().unwrap();
        let cfg = dir.path().join("configuration.nix");
        std::fs::write(
            &cfg,
            "  systemd.sysusers.enable = false;\n  users.users.exp = {\n  };\n",
        )
        .unwrap();
        let input = HookInput {
            tool_name: "Write".to_string(),
            tool_input: ToolInput {
                file_path: cfg.display().to_string(),
                content: "  users.users.exp = {\n  };\n".to_string(),
                ..Default::default()
            },
            ..Default::default()
        };
        let reason = check_write(&input, &compiled_patterns()).unwrap();
        assert!(reason.contains("sysusers"));
    }

    #[test]
    fn write_allows_preserved_protected_lines() {
        let dir = tempdir().unwrap();
        let cfg = dir.path().join("configuration.nix");
        let content = "  systemd.sysusers.enable = false;\n    initialPassword = \"pa\";\n";
        std::fs::write(&cfg, content).unwrap();
        let input = HookInput {
            tool_name: "Write".to_string(),
            tool_input: ToolInput {
                file_path: cfg.display().to_string(),
                content: content.to_string(),
                ..Default::default()
            },
            ..Default::default()
        };
        assert_eq!(check_write(&input, &compiled_patterns()), None);
    }
}
