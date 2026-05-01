use serde_json::{Map, Value, json};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

fn read_api_key(root: &Path) -> io::Result<String> {
    Ok(fs::read_to_string(root.join(".env"))?.trim().to_string())
}

fn hook(command: String, timeout: Option<u64>) -> Value {
    let mut hook = Map::new();
    hook.insert("type".to_string(), Value::String("command".to_string()));
    hook.insert("command".to_string(), Value::String(command));
    if let Some(timeout) = timeout {
        hook.insert("timeout".to_string(), Value::from(timeout));
    }
    Value::Object(hook)
}

fn unix_path(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn linux_hook(binary_path: &Path, subcommand: &str, timeout: Option<u64>) -> Value {
    hook(format!("{} {subcommand}", binary_path.display()), timeout)
}

fn windows_hook(binary_path: &Path, subcommand: &str, timeout: Option<u64>) -> Value {
    hook(
        format!("\"{}\" {subcommand}", unix_path(binary_path)),
        timeout,
    )
}

fn common_object(common: Value) -> Map<String, Value> {
    match common {
        Value::Object(map) => map,
        _ => Map::new(),
    }
}

pub fn build_common_config_with_api_key(api_key: &str) -> Value {
    json!({
        "skipDangerousModePermissionPrompt": true,
        "effortLevel": "max",
        "env": {
            "ANTHROPIC_AUTH_TOKEN": api_key,
            "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
            "ANTHROPIC_MODEL": "glm-5.1",
            "API_TIMEOUT_MS": "3000000",
        },
    })
}

pub fn build_common_config(root: &Path) -> io::Result<Value> {
    Ok(build_common_config_with_api_key(&read_api_key(root)?))
}

pub fn build_linux_config(common: Value, binary_path: &Path, _home: &Path) -> Value {
    let mut config = common_object(common);
    config.insert(
        "permissions".to_string(),
        json!({
            "defaultMode": "bypassPermissions",
            "deny": ["Agent"],
        }),
    );
    config.insert("language".to_string(), Value::String("ja".to_string()));
    config.insert("voiceEnabled".to_string(), Value::Bool(true));
    config.insert("spinnerTipsEnabled".to_string(), Value::Bool(false));
    config.insert("prefersReducedMotion".to_string(), Value::Bool(true));
    config.insert(
        "hooks".to_string(),
        json!({
            "PreToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        linux_hook(binary_path, "block-settings-json-direct-edit", None),
                        linux_hook(binary_path, "block-protected-nix-config", None),
                        linux_hook(binary_path, "block-non-python-hook-scripts", None),
                        linux_hook(binary_path, "block-any-type", None),
                        linux_hook(binary_path, "block-setup-py-cfg", None),
                        linux_hook(binary_path, "block-manual-requirements-txt", None),
                        linux_hook(binary_path, "block-wildcard-versions", None),
                        linux_hook(binary_path, "block-missing-annotations", None),
                        linux_hook(binary_path, "block-unbounded-dependency", None),
                    ],
                },
                {
                    "matcher": "Write|Bash",
                    "hooks": [
                        linux_hook(binary_path, "block-platform-specific-scripts", None),
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        linux_hook(binary_path, "block-git-add-force-staging", None),
                        linux_hook(binary_path, "block-git-commit-prohibited-keywords", None),
                        linux_hook(binary_path, "block-commit-without-verification", Some(120)),
                        linux_hook(binary_path, "block-git-commit-protected-changes", None),
                        linux_hook(binary_path, "block-nixos-rebuild-protected-changes", None),
                        linux_hook(binary_path, "block-prohibited-python-toolchains", None),
                        linux_hook(binary_path, "block-install-without-lock", None),
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        linux_hook(binary_path, "post-auto-setup", None),
                    ],
                },
                {
                    "matcher": "Edit|Write|Bash",
                    "hooks": [
                        linux_hook(binary_path, "post-verify-protected-nix-config", None),
                    ],
                },
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        linux_hook(binary_path, "post-cargo-clippy-on-rs-edit", Some(120)),
                        linux_hook(binary_path, "post-oxisym-scan", Some(120)),
                        linux_hook(binary_path, "warn-hardcoded-paths", None),
                        linux_hook(binary_path, "warn-structural-duplicates", None),
                        linux_hook(binary_path, "warn-gitignore-not-whitelist", None),
                        linux_hook(binary_path, "block-magic-numbers", None),
                        linux_hook(binary_path, "check-hotstring-conflicts", None),
                        linux_hook(binary_path, "block-worker-in-tracked-datasource", None),
                        linux_hook(binary_path, "block-scrape-interval", None),
                        linux_hook(binary_path, "post-scan-fallbacks", None),
                    ],
                },
            ],
            "Stop": [
                {
                    "hooks": [
                        linux_hook(binary_path, "stop-lint-edited-python", Some(300)),
                        linux_hook(binary_path, "stop-require-git-commit-and-push", Some(15)),
                        linux_hook(binary_path, "stop-nixos-rebuild-on-config-change", Some(300)),
                        linux_hook(binary_path, "stop-require-source-verification", Some(15)),
                        linux_hook(binary_path, "stop-scan-error-handling", Some(15)),
                        linux_hook(binary_path, "stop-scan-any-type", Some(15)),
                        linux_hook(binary_path, "stop-warn-chrome-tabs", Some(15)),
                        linux_hook(binary_path, "stop-prompt-architecture-md", Some(15)),
                        linux_hook(binary_path, "stop-update-and-patch-claude", Some(120)),
                    ],
                },
            ],
        }),
    );
    Value::Object(config)
}

pub fn build_windows_config(common: Value, binary_path: &Path, home: &Path) -> Value {
    let claude_home_bs = home.join(".claude").to_string_lossy().to_string();
    let mut config = common_object(common);
    config.insert(
        "permissions".to_string(),
        json!({
            "allow": ["Edit", "Write", "Read", "Bash", "Grep", "Glob"],
            "deny": ["Task", "Agent"],
            "defaultMode": "bypassPermissions",
        }),
    );
    config.insert("spinnerTipsEnabled".to_string(), Value::Bool(false));
    config.insert("prefersReducedMotion".to_string(), Value::Bool(true));
    config.insert(
        "hooks".to_string(),
        json!({
            "PreToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        windows_hook(binary_path, "block-settings-json-direct-edit", None),
                        windows_hook(binary_path, "block-non-python-hook-scripts", None),
                        windows_hook(binary_path, "block-any-type", None),
                        windows_hook(binary_path, "block-setup-py-cfg", None),
                        windows_hook(binary_path, "block-manual-requirements-txt", None),
                        windows_hook(binary_path, "block-wildcard-versions", None),
                        windows_hook(binary_path, "block-missing-annotations", None),
                        windows_hook(binary_path, "block-unbounded-dependency", None),
                    ],
                },
                {
                    "matcher": "Write|Bash",
                    "hooks": [
                        windows_hook(binary_path, "block-platform-specific-scripts", None),
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        windows_hook(binary_path, "block-git-add-force-staging", None),
                        windows_hook(binary_path, "block-git-commit-prohibited-keywords", None),
                        windows_hook(binary_path, "block-commit-without-verification", Some(120)),
                        windows_hook(binary_path, "block-prohibited-python-toolchains", None),
                        windows_hook(binary_path, "block-install-without-lock", None),
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        windows_hook(binary_path, "post-auto-setup", None),
                    ],
                },
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        windows_hook(binary_path, "post-cargo-clippy-on-rs-edit", Some(120)),
                        windows_hook(binary_path, "post-oxisym-scan", Some(120)),
                        windows_hook(binary_path, "check-hotstring-conflicts", None),
                        windows_hook(binary_path, "warn-hardcoded-paths", None),
                        windows_hook(binary_path, "warn-structural-duplicates", None),
                        windows_hook(binary_path, "warn-gitignore-not-whitelist", None),
                        windows_hook(binary_path, "block-magic-numbers", None),
                        windows_hook(binary_path, "block-worker-in-tracked-datasource", None),
                        windows_hook(binary_path, "block-scrape-interval", None),
                        windows_hook(binary_path, "post-scan-fallbacks", None),
                    ],
                },
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        windows_hook(binary_path, "stop-require-git-commit-and-push", Some(15)),
                        windows_hook(binary_path, "stop-require-source-verification", Some(15)),
                        windows_hook(binary_path, "stop-scan-error-handling", Some(15)),
                        windows_hook(binary_path, "stop-scan-any-type", Some(15)),
                        windows_hook(binary_path, "stop-prompt-architecture-md", Some(15)),
                        windows_hook(binary_path, "stop-update-and-patch-claude", Some(120)),
                        hook(
                            format!(
                                "pwsh -NoProfile -ExecutionPolicy Bypass -File \"{claude_home_bs}\\scripts\\notify-complete.ps1\""
                            ),
                            None,
                        ),
                    ],
                },
            ],
        }),
    );
    Value::Object(config)
}

pub fn write_settings(
    root: &Path,
    system: &str,
    common: Option<Value>,
    binary_path: &Path,
) -> io::Result<PathBuf> {
    let home = root.parent().unwrap_or(root);
    let common = match common {
        Some(value) => value,
        None => build_common_config(root)?,
    };
    let config = match system {
        "Linux" => build_linux_config(common, binary_path, home),
        "Windows" => build_windows_config(common, binary_path, home),
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("Unsupported OS: {system}"),
            ));
        }
    };
    let target = root.join("settings.json");
    let rendered = serde_json::to_string_pretty(&config).map_err(io::Error::other)? + "\n";
    fs::write(&target, rendered)?;
    Ok(target)
}

pub fn main() -> i32 {
    let root = match std::env::current_dir() {
        Ok(path) => path,
        Err(err) => {
            eprintln!("{err}");
            return 1;
        }
    };
    let system = match std::env::consts::OS {
        "linux" => "Linux",
        "windows" => "Windows",
        other => {
            eprintln!("Unsupported OS: {other}");
            return 1;
        }
    };
    let binary_path = match std::env::current_exe() {
        Ok(path) => path,
        Err(err) => {
            eprintln!("{err}");
            return 1;
        }
    };
    match write_settings(&root, system, None, &binary_path) {
        Ok(path) => {
            println!("Generated: {}", path.display());
            0
        }
        Err(err) => {
            eprintln!("{err}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        build_common_config_with_api_key, build_linux_config, build_windows_config, write_settings,
    };
    use serde_json::{Value, json};
    use std::collections::BTreeSet;
    use std::path::{Path, PathBuf};
    use tempfile::tempdir;

    fn project_root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .to_path_buf()
    }

    fn home_dir() -> PathBuf {
        project_root().parent().unwrap().to_path_buf()
    }

    fn binary_path() -> PathBuf {
        project_root().join("hooks-rs/target/debug/claude-hooks")
    }

    fn linux_config() -> Value {
        build_linux_config(
            build_common_config_with_api_key("test-key"),
            &binary_path(),
            &home_dir(),
        )
    }

    fn windows_config() -> Value {
        build_windows_config(
            build_common_config_with_api_key("test-key"),
            &binary_path(),
            &home_dir(),
        )
    }

    fn validate_hook_entry(entry: &Value, context: &str) {
        assert_eq!(
            entry["type"].as_str(),
            Some("command"),
            "{context}: type must be command"
        );
        assert!(
            entry["command"]
                .as_str()
                .is_some_and(|value| !value.is_empty()),
            "{context}: empty command"
        );
    }

    fn validate_hook_group(group: &Value, context: &str) {
        let hooks = group["hooks"].as_array().expect("hooks array");
        assert!(!hooks.is_empty(), "{context}: empty hooks list");
        for (index, entry) in hooks.iter().enumerate() {
            validate_hook_entry(entry, &format!("{context}[{index}]"));
        }
    }

    fn validate_config(config: &Value, os_name: &str) {
        assert!(
            config.get("permissions").is_some(),
            "{os_name}: missing permissions"
        );
        assert_eq!(
            config["skipDangerousModePermissionPrompt"].as_bool(),
            Some(true),
            "{os_name}: skipDangerousModePermissionPrompt must be true"
        );
        assert!(config.get("hooks").is_some(), "{os_name}: missing hooks");
        assert_eq!(
            config["permissions"]["defaultMode"].as_str(),
            Some("bypassPermissions")
        );

        for category in ["PreToolUse", "PostToolUse", "Stop"] {
            let groups = config["hooks"][category].as_array().expect("group array");
            assert!(!groups.is_empty(), "{os_name}: empty {category}");
            for (index, group) in groups.iter().enumerate() {
                validate_hook_group(group, &format!("{os_name}/{category}[{index}]"));
            }
        }

        let serialized = serde_json::to_string_pretty(config).unwrap();
        let roundtrip: Value = serde_json::from_str(&serialized).unwrap();
        assert_eq!(roundtrip, *config, "{os_name}: JSON round-trip mismatch");
    }

    fn check_both_have_hook(linux: &Value, windows: &Value, subcommand: &str) {
        for (os_name, config) in [("Linux", linux), ("Windows", windows)] {
            let found = config["hooks"]
                .as_object()
                .unwrap()
                .values()
                .flat_map(|groups| groups.as_array().unwrap())
                .flat_map(|group| group["hooks"].as_array().unwrap())
                .any(|hook| {
                    hook["command"]
                        .as_str()
                        .is_some_and(|command| command.ends_with(subcommand))
                });
            assert!(found, "{os_name} config missing {subcommand}");
        }
    }

    fn all_hook_targets(config: &Value) -> Vec<String> {
        let mut targets = Vec::new();
        for groups in config["hooks"].as_object().unwrap().values() {
            for group in groups.as_array().unwrap() {
                for hook in group["hooks"].as_array().unwrap() {
                    let command = hook["command"].as_str().unwrap();
                    let last = command.split_whitespace().last().unwrap().trim_matches('"');
                    if last.ends_with(".ps1") {
                        let normalized = last.replace('\\', "/");
                        targets.push(
                            Path::new(&normalized)
                                .file_name()
                                .unwrap()
                                .to_string_lossy()
                                .to_string(),
                        );
                    } else {
                        targets.push(last.to_string());
                    }
                }
            }
        }
        targets
    }

    fn available_subcommands() -> BTreeSet<String> {
        let main_rs = std::fs::read_to_string(project_root().join("hooks-rs/src/main.rs")).unwrap();
        main_rs
            .lines()
            .filter_map(|line| {
                let trimmed = line.trim_start();
                trimmed
                    .strip_prefix('"')
                    .and_then(|rest| rest.split_once('"'))
                    .map(|(name, _)| name.to_string())
            })
            .collect()
    }

    #[test]
    fn linux_config_structure() {
        validate_config(&linux_config(), "Linux");
    }

    #[test]
    fn windows_config_structure() {
        validate_config(&windows_config(), "Windows");
    }

    #[test]
    fn linux_deny_list() {
        assert_eq!(linux_config()["permissions"]["deny"], json!(["Agent"]));
    }

    #[test]
    fn linux_hooks_use_unquoted_paths() {
        for group in linux_config()["hooks"]["PreToolUse"].as_array().unwrap() {
            for hook in group["hooks"].as_array().unwrap() {
                assert!(
                    !hook["command"].as_str().unwrap().contains('"'),
                    "Linux hook commands should not have quoted paths"
                );
            }
        }
    }

    #[test]
    fn windows_effort_level_max() {
        assert_eq!(
            windows_config()["effortLevel"],
            Value::String("max".to_string())
        );
    }

    #[test]
    fn windows_deny_list() {
        assert_eq!(
            windows_config()["permissions"]["deny"],
            json!(["Task", "Agent"])
        );
    }

    #[test]
    fn windows_hooks_use_quoted_paths() {
        for group in windows_config()["hooks"]["PreToolUse"].as_array().unwrap() {
            for hook in group["hooks"].as_array().unwrap() {
                assert!(
                    hook["command"].as_str().unwrap().contains('"'),
                    "Windows hook commands should have quoted paths"
                );
            }
        }
    }

    #[test]
    fn windows_stop_has_powershell_notify() {
        let has_pwsh = windows_config()["hooks"]["Stop"]
            .as_array()
            .unwrap()
            .iter()
            .flat_map(|group| group["hooks"].as_array().unwrap())
            .any(|hook| hook["command"].as_str().unwrap().contains("pwsh"));
        assert!(has_pwsh, "Windows Stop should have pwsh notify-complete");
    }

    #[test]
    fn both_have_block_git_add_force() {
        let linux = linux_config();
        let windows = windows_config();
        check_both_have_hook(&linux, &windows, "block-git-add-force-staging");
    }

    #[test]
    fn both_have_block_non_python_hooks() {
        let linux = linux_config();
        let windows = windows_config();
        check_both_have_hook(&linux, &windows, "block-non-python-hook-scripts");
    }

    #[test]
    fn common_config_included() {
        let common = build_common_config_with_api_key("test-key");
        let linux = build_linux_config(common.clone(), &binary_path(), &home_dir());
        let windows = build_windows_config(common.clone(), &binary_path(), &home_dir());
        for (key, value) in common.as_object().unwrap() {
            assert_eq!(
                linux.get(key),
                Some(value),
                "Linux missing common key {key}"
            );
            assert_eq!(
                windows.get(key),
                Some(value),
                "Windows missing common key {key}"
            );
        }
    }

    #[test]
    fn shared_hooks_present_in_both() {
        let os_specific = [
            "block-protected-nix-config",
            "block-git-commit-protected-changes",
            "block-nixos-rebuild-protected-changes",
            "post-verify-protected-nix-config",
            "stop-nixos-rebuild-on-config-change",
            "stop-lint-edited-python",
            "stop-warn-chrome-tabs",
            "check-hotstring-conflicts",
            "notify-complete.ps1",
        ];
        let linux_scripts: BTreeSet<_> = all_hook_targets(&linux_config())
            .into_iter()
            .filter(|script| !os_specific.contains(&script.as_str()))
            .collect();
        let windows_scripts: BTreeSet<_> = all_hook_targets(&windows_config())
            .into_iter()
            .filter(|script| !os_specific.contains(&script.as_str()))
            .collect();
        let only_linux: Vec<_> = linux_scripts
            .difference(&windows_scripts)
            .cloned()
            .collect();
        let only_windows: Vec<_> = windows_scripts
            .difference(&linux_scripts)
            .cloned()
            .collect();
        assert!(
            only_linux.is_empty(),
            "Registered in Linux only: {only_linux:?}"
        );
        assert!(
            only_windows.is_empty(),
            "Registered in Windows only: {only_windows:?}"
        );
    }

    #[test]
    fn linux_hook_commands_exist() {
        let subcommands = available_subcommands();
        for script in all_hook_targets(&linux_config()) {
            if script.ends_with(".ps1") {
                continue;
            }
            assert!(
                subcommands.contains(&script),
                "Linux references missing hook command: {script}"
            );
        }
    }

    #[test]
    fn windows_hook_commands_exist() {
        let subcommands = available_subcommands();
        for script in all_hook_targets(&windows_config()) {
            if script.ends_with(".ps1") {
                continue;
            }
            assert!(
                subcommands.contains(&script),
                "Windows references missing hook command: {script}"
            );
        }
    }

    #[test]
    fn write_settings_writes_json_file() {
        let temp = tempdir().unwrap();
        let root = temp.path().join(".claude");
        std::fs::create_dir_all(&root).unwrap();
        let target = write_settings(
            &root,
            "Linux",
            Some(build_common_config_with_api_key("written-key")),
            &binary_path(),
        )
        .unwrap();
        assert_eq!(target, root.join("settings.json"));
        let content = std::fs::read_to_string(target).unwrap();
        assert!(content.contains("\"written-key\""));
        assert!(content.contains("claude-hooks"));
        assert!(content.ends_with('\n'));
    }
}
