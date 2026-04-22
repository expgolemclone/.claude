use crate::git::run_git;
use crate::input::HookInput;
use crate::output::block;

pub fn run(input: &HookInput) {
    if input.permission_mode == "plan" {
        return;
    }

    let nix_config = home::home_dir().unwrap_or_default().join("nix-config");
    let status = run_git(&nix_config, &["status", "--porcelain"]);
    if !status.is_empty() {
        return;
    }

    let head_hash = run_git(&nix_config, &["rev-parse", "HEAD"]);
    if head_hash.is_empty() {
        return;
    }

    let hash_file = std::env::temp_dir().join(".nix-config-last-rebuild-hash");
    let last_hash = std::fs::read_to_string(&hash_file)
        .unwrap_or_default()
        .trim()
        .to_string();
    if head_hash == last_hash {
        return;
    }

    let result = std::process::Command::new("sudo")
        .args(["nixos-rebuild", "switch", "--flake"])
        .arg(format!("{}#nixos", nix_config.display()))
        .output();

    match result {
        Ok(o) if o.status.success() => {
            let _ = std::fs::write(&hash_file, &head_hash);
        }
        Ok(o) => {
            let stderr = String::from_utf8_lossy(&o.stderr).to_string();
            block(&format!("nixos-rebuild failed:\n{stderr}"));
        }
        Err(_) => {}
    }
}
