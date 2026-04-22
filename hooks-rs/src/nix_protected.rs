use regex::Regex;

pub const PROTECTED_PATTERNS: &[&str] = &[
    r"sysusers\.enable",
    r"userborn\.enable",
    r"mutableUsers",
    r"initialPassword",
    r"hashedPassword",
    r"password\s*=",
];

pub fn check_config_diff(diff_text: &str) -> Option<String> {
    let compiled: Vec<Regex> = PROTECTED_PATTERNS
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect();
    let mut in_config_file = false;
    for line in diff_text.lines() {
        if line.starts_with("diff --git") {
            in_config_file = line.contains("configuration.nix");
            continue;
        }
        if !in_config_file {
            continue;
        }
        if !line.starts_with('+') && !line.starts_with('-') {
            continue;
        }
        if line.starts_with("+++") || line.starts_with("---") {
            continue;
        }
        for (i, re) in compiled.iter().enumerate() {
            if re.is_match(line) {
                return Some(format!(
                    "configuration.nix の保護対象行が変更されています: {}\n変更行: {}",
                    PROTECTED_PATTERNS[i],
                    line.trim()
                ));
            }
        }
    }
    None
}

pub fn check_mkforce_override(diff_text: &str) -> Option<String> {
    let compiled: Vec<Regex> = PROTECTED_PATTERNS
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect();
    let mut in_config_file = false;
    for line in diff_text.lines() {
        if line.starts_with("diff --git") {
            in_config_file = line.contains("configuration.nix");
            continue;
        }
        if !in_config_file || !line.starts_with('+') || line.starts_with("+++") {
            continue;
        }
        if !line.contains("mkForce") {
            continue;
        }
        for re in &compiled {
            if re.is_match(line) {
                return Some(format!(
                    "mkForce で保護対象の設定を上書きしようとしています: {}",
                    line.trim()
                ));
            }
        }
    }
    None
}
