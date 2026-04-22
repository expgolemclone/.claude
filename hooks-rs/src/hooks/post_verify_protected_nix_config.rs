use regex::Regex;
use sha2::{Digest, Sha256};

use crate::input::HookInput;
use crate::nix_protected::PROTECTED_PATTERNS;
use crate::output::block;

pub fn run(_input: &HookInput) {
    let config_path = home::home_dir()
        .unwrap_or_default()
        .join("nix-config")
        .join("hosts")
        .join("nixos")
        .join("configuration.nix");
    if !config_path.exists() {
        return;
    }

    let content = match std::fs::read_to_string(&config_path) {
        Ok(c) => c,
        Err(_) => return,
    };

    let compiled: Vec<Regex> = PROTECTED_PATTERNS
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect();

    let mut protected_lines: Vec<String> = Vec::new();
    for line in content.lines() {
        for re in &compiled {
            if re.is_match(line) {
                protected_lines.push(line.trim().to_string());
                break;
            }
        }
    }
    protected_lines.sort();

    if protected_lines.is_empty() {
        return;
    }

    let current_hash = {
        let mut hasher = Sha256::new();
        hasher.update(protected_lines.join("\n").as_bytes());
        format!("{:x}", hasher.finalize())
    };

    let hash_file = std::env::temp_dir().join(".nix-config-protected-hash");
    if !hash_file.exists() {
        let _ = std::fs::write(&hash_file, &current_hash);
        return;
    }

    let saved_hash = std::fs::read_to_string(&hash_file)
        .unwrap_or_default()
        .trim()
        .to_string();
    if current_hash == saved_hash {
        return;
    }

    block(&format!(
        "configuration.nix の保護対象行が変更されました。\n変更を元に戻してください: git checkout hosts/nixos/configuration.nix\n保護行: {:?}",
        protected_lines
    ));
}
