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

#[cfg(test)]
mod tests {
    use super::{check_config_diff, check_mkforce_override};

    const DIFF_SYSUSERS_CHANGED: &str = "\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -156,7 +156,7 @@
  # --- ユーザー ---
-  systemd.sysusers.enable = false;
+  systemd.sysusers.enable = true;
  users.users.exp = {
";

    const DIFF_PASSWORD_REMOVED: &str = "\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -160,7 +160,6 @@
    extraGroups = [ \"networkmanager\" \"wheel\" ];
    shell = pkgs.zsh;
-    initialPassword = \"pa\";
  };
";

    const DIFF_SAFE_CHANGE: &str = "\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -170,7 +170,7 @@
  fonts.packages = with pkgs; [
-    noto-fonts
+    noto-fonts-cjk-sans
  ];
";

    const DIFF_OTHER_FILE: &str = "\
diff --git a/home/home.nix b/home/home.nix
--- a/home/home.nix
+++ b/home/home.nix
@@ -1,3 +1,3 @@
-  password = \"old\";
+  password = \"new\";
";

    const DIFF_MKFORCE_OVERRIDE: &str = "\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -156,6 +156,9 @@
+{ lib, ... }: {
+  systemd.sysusers.enable = lib.mkForce true;
+}
";

    const DIFF_MKFORCE_SAFE: &str = "\
diff --git a/modules/safe.nix b/modules/safe.nix
--- /dev/null
+++ b/modules/safe.nix
@@ -0,0 +1,3 @@
+{ lib, ... }: {
+  services.nginx.enable = lib.mkForce true;
+}
";

    #[test]
    fn config_diff_detects_sysusers_change() {
        let result = check_config_diff(DIFF_SYSUSERS_CHANGED).unwrap();
        assert!(result.contains("sysusers"));
    }

    #[test]
    fn config_diff_detects_password_removal() {
        let result = check_config_diff(DIFF_PASSWORD_REMOVED).unwrap();
        assert!(result.contains("initialPassword"));
    }

    #[test]
    fn config_diff_ignores_safe_change() {
        assert_eq!(check_config_diff(DIFF_SAFE_CHANGE), None);
    }

    #[test]
    fn config_diff_ignores_other_file() {
        assert_eq!(check_config_diff(DIFF_OTHER_FILE), None);
    }

    #[test]
    fn mkforce_detects_protected_override() {
        let result = check_mkforce_override(DIFF_MKFORCE_OVERRIDE).unwrap();
        assert!(result.contains("mkForce"));
    }

    #[test]
    fn mkforce_ignores_safe_override() {
        assert_eq!(check_mkforce_override(DIFF_MKFORCE_SAFE), None);
    }
}
