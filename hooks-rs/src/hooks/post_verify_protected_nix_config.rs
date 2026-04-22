use regex::Regex;
use sha2::{Digest, Sha256};

use crate::input::HookInput;
use crate::nix_protected::PROTECTED_PATTERNS;
use crate::output::block;

fn extract_protected_lines(content: &str) -> Vec<String> {
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
    protected_lines
}

fn compute_hash(lines: &[String]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(lines.join("\n").as_bytes());
    format!("{:x}", hasher.finalize())
}

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

    let protected_lines = extract_protected_lines(&content);
    if protected_lines.is_empty() {
        return;
    }

    let current_hash = compute_hash(&protected_lines);

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

#[cfg(test)]
mod tests {
    use super::{compute_hash, extract_protected_lines};

    const GOOD_CONFIG: &str = "\
  # --- ユーザー ---
  systemd.sysusers.enable = false;
  users.users.exp = {
    initialPassword = \"pa\";
  };
";

    const NO_PROTECTED_CONFIG: &str = "\
  networking.hostName = \"nixos\";
  time.timeZone = \"Asia/Tokyo\";
";

    #[test]
    fn extracts_protected_lines() {
        let lines = extract_protected_lines(GOOD_CONFIG);
        assert!(lines.iter().any(|line| line.contains("sysusers")));
        assert!(lines.iter().any(|line| line.contains("initialPassword")));
    }

    #[test]
    fn returns_empty_when_no_protected_lines_exist() {
        assert!(extract_protected_lines(NO_PROTECTED_CONFIG).is_empty());
    }

    #[test]
    fn extracted_lines_are_sorted() {
        let lines = extract_protected_lines(GOOD_CONFIG);
        let mut sorted = lines.clone();
        sorted.sort();
        assert_eq!(lines, sorted);
    }

    #[test]
    fn identical_lines_have_same_hash() {
        let lines = vec!["a".to_string(), "b".to_string()];
        assert_eq!(compute_hash(&lines), compute_hash(&lines));
    }

    #[test]
    fn different_lines_have_different_hashes() {
        assert_ne!(
            compute_hash(&["a".to_string()]),
            compute_hash(&["b".to_string()])
        );
    }
}
