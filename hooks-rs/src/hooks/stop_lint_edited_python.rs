use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::{self, Write};
use std::path::Path;
use std::time::Duration;

use crate::input::HookInput;
use crate::process::{CommandError, combined_output, output_with_timeout};

fn config_dir() -> std::path::PathBuf {
    home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join("config")
}

fn hooks_dir() -> std::path::PathBuf {
    home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join("hooks")
}

fn cache_file() -> std::path::PathBuf {
    home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join(".cache")
        .join("lint-hashes.json")
}

fn load_toml(filename: &str) -> Option<toml::Value> {
    let path = config_dir().join(filename);
    let content = std::fs::read_to_string(&path).ok()?;
    toml::from_str(&content).ok()
}

fn file_sha256(path: &Path) -> String {
    let mut hasher = Sha256::new();
    if let Ok(bytes) = std::fs::read(path) {
        hasher.update(&bytes);
    }
    format!("{:x}", hasher.finalize())
}

fn all_py_files() -> Vec<std::path::PathBuf> {
    let hooks = hooks_dir();
    let mut files = Vec::new();
    collect_py_files(&hooks, &mut files);
    files.sort();
    files
}

fn collect_py_files(dir: &Path, files: &mut Vec<std::path::PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_py_files(&path, files);
        } else if path.extension().and_then(|e| e.to_str()) == Some("py") {
            files.push(path);
        }
    }
}

fn load_cache() -> HashMap<String, String> {
    let content = match std::fs::read_to_string(cache_file()) {
        Ok(c) => c,
        Err(_) => return HashMap::new(),
    };
    serde_json::from_str(&content).unwrap_or_default()
}

fn save_cache(hashes: &HashMap<String, String>) {
    let path = cache_file();
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(json) = serde_json::to_string_pretty(hashes) {
        let _ = std::fs::write(&path, json);
    }
}

fn changed_files(
    cached: &HashMap<String, String>,
) -> (Vec<std::path::PathBuf>, HashMap<String, String>) {
    let mut current = HashMap::new();
    let mut changed = Vec::new();
    for p in all_py_files() {
        let key = p.display().to_string();
        let digest = file_sha256(&p);
        current.insert(key.clone(), digest.clone());
        if cached.get(&key) != Some(&digest) {
            changed.push(p);
        }
    }
    (changed, current)
}

fn build_commands(
    files: &[std::path::PathBuf],
    cli_cfg: &toml::Value,
) -> Vec<(&'static str, Vec<String>)> {
    let linters = match cli_cfg.get("python_linters") {
        Some(v) => v,
        None => return Vec::new(),
    };
    let runner = linters
        .get("runner")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect::<Vec<_>>()
        })
        .unwrap_or_else(|| vec!["uv".into(), "run".into()]);
    let warn_flag = linters
        .get("python_warning_flag")
        .and_then(|v| v.as_str())
        .unwrap_or("error");
    let tools = match linters.get("tools") {
        Some(v) => v,
        None => return Vec::new(),
    };

    let file_strs: Vec<String> = files.iter().map(|f| f.display().to_string()).collect();
    let mut commands = Vec::new();

    for name in &["mypy", "ruff", "pylint"] {
        let tool_cfg = match tools.get(*name) {
            Some(v) => v,
            None => continue,
        };
        let extra_args: Vec<String> = tool_cfg
            .get("args")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let command_opt: Option<Vec<String>> =
            tool_cfg.get("command").and_then(|v| v.as_array()).map(|a| {
                a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            });

        let cmd = if let Some(command) = command_opt {
            [&command[..], &extra_args[..], &file_strs[..]].concat()
        } else {
            let module = tool_cfg
                .get("module")
                .and_then(|v| v.as_str())
                .unwrap_or(name);
            let mut base = runner.clone();
            base.extend([
                "python3".into(),
                "-W".into(),
                warn_flag.into(),
                "-m".into(),
                module.into(),
            ]);
            base.extend(extra_args);
            base.extend(file_strs.clone());
            base
        };
        commands.push((*name, cmd));
    }
    commands
}

fn run_commands(
    commands: &[(&str, Vec<String>)],
    project_root: &Path,
    timeout: Duration,
    timeout_label: &str,
) -> Vec<String> {
    let mut diagnostics = Vec::new();

    for (name, cmd) in commands {
        if cmd.is_empty() {
            continue;
        }

        let mut command = std::process::Command::new(&cmd[0]);
        command.args(&cmd[1..]).current_dir(project_root);

        match output_with_timeout(&mut command, timeout) {
            Ok(output) => {
                let text = combined_output(&output);
                if !output.status.success() && !text.is_empty() {
                    diagnostics.push(format!("[{name}]\n{text}"));
                }
            }
            Err(CommandError::TimedOut) => {
                diagnostics.push(format!("[{name}] timed out after {timeout_label}"));
            }
            Err(CommandError::Io(_)) => {
                diagnostics.push(format!("[{name}] runner not found"));
            }
        }
    }

    diagnostics
}

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }

    let cli_cfg = match load_toml("cli_defaults.toml") {
        Some(v) => v,
        None => return,
    };
    let magic_cfg = load_toml("magic_numbers.toml");
    let timeout: u64 = magic_cfg
        .as_ref()
        .and_then(|c| c.get("python_linters"))
        .and_then(|l| l.get("timeout_seconds"))
        .and_then(|v| v.as_integer())
        .unwrap_or(120) as u64;
    let timeout_duration = Duration::from_secs(timeout);
    let timeout_label = format!("{timeout}s");

    let cached = load_cache();
    let (files, current_hashes) = changed_files(&cached);
    if files.is_empty() {
        return;
    }

    let commands = build_commands(&files, &cli_cfg);
    let project_root = home::home_dir().unwrap_or_default().join(".claude");
    let diagnostics = run_commands(&commands, &project_root, timeout_duration, &timeout_label);

    if !diagnostics.is_empty() {
        let msg = json!({"decision": "block", "reason": format!("Python lint errors detected:\n\n{}\n\nFix these issues.", diagnostics.join("\n\n"))});
        let _ = writeln!(io::stdout(), "{msg}");
    } else {
        save_cache(&current_hashes);
    }
}

#[cfg(test)]
mod tests {
    use super::{build_commands, file_sha256, run_commands};
    use std::path::PathBuf;
    use std::time::Duration;
    use tempfile::tempdir;

    #[test]
    fn timeout_is_reported_for_hung_linter() {
        let commands = vec![(
            "slow",
            vec![
                "python3".to_string(),
                "-c".to_string(),
                "import time; time.sleep(2)".to_string(),
            ],
        )];

        let diagnostics = run_commands(
            &commands,
            tempdir().unwrap().path(),
            Duration::from_millis(100),
            "100ms",
        );

        assert_eq!(diagnostics, vec!["[slow] timed out after 100ms"]);
    }

    #[test]
    fn build_commands_supports_module_mode() {
        let test_file = PathBuf::from("/tmp/test.py");
        let cli_cfg: toml::Value = toml::from_str(
            r#"
[python_linters]
python_warning_flag = "error"
runner = ["uv", "run"]

[python_linters.tools.mypy]
module = "mypy"

[python_linters.tools.ruff]
module = "ruff"
args = ["check"]

[python_linters.tools.pylint]
module = "pylint"
"#,
        )
        .unwrap();

        let commands = build_commands(&[test_file.clone()], &cli_cfg);
        assert_eq!(
            commands[0].1,
            vec![
                "uv",
                "run",
                "python3",
                "-W",
                "error",
                "-m",
                "mypy",
                test_file.to_string_lossy().as_ref()
            ]
        );
        assert_eq!(
            commands[1].1,
            vec![
                "uv",
                "run",
                "python3",
                "-W",
                "error",
                "-m",
                "ruff",
                "check",
                test_file.to_string_lossy().as_ref()
            ]
        );
    }

    #[test]
    fn build_commands_supports_command_mode() {
        let test_file = PathBuf::from("/tmp/test.py");
        let cli_cfg: toml::Value = toml::from_str(
            r#"
[python_linters]
python_warning_flag = "error"
runner = ["uv", "run"]

[python_linters.tools.mypy]
module = "mypy"

[python_linters.tools.ruff]
command = ["nix", "run", "nixpkgs#ruff", "--"]
args = ["check"]

[python_linters.tools.pylint]
module = "pylint"
"#,
        )
        .unwrap();

        let commands = build_commands(&[test_file.clone()], &cli_cfg);
        assert_eq!(
            commands[1].1,
            vec![
                "nix",
                "run",
                "nixpkgs#ruff",
                "--",
                "check",
                test_file.to_string_lossy().as_ref()
            ]
        );
    }

    #[test]
    fn file_sha256_changes_with_content() {
        let dir = tempdir().unwrap();
        let file = dir.path().join("a.py");
        std::fs::write(&file, "a: int = 1\n").unwrap();
        let before = file_sha256(&file);
        std::fs::write(&file, "a: int = 2\n").unwrap();
        let after = file_sha256(&file);

        assert_ne!(before, after);
    }
}
