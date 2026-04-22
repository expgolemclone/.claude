use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::{self, Write};
use std::path::Path;

use crate::input::HookInput;

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

    let cached = load_cache();
    let (files, current_hashes) = changed_files(&cached);
    if files.is_empty() {
        return;
    }

    let commands = build_commands(&files, &cli_cfg);
    let mut diagnostics = Vec::new();

    let project_root = home::home_dir().unwrap_or_default().join(".claude");

    for (name, cmd) in commands {
        let result = std::process::Command::new(&cmd[0])
            .args(&cmd[1..])
            .current_dir(&project_root)
            .output();
        match result {
            Ok(o) => {
                let stdout = String::from_utf8_lossy(&o.stdout).trim().to_string();
                let stderr = String::from_utf8_lossy(&o.stderr).trim().to_string();
                let output = if stdout.is_empty() {
                    stderr
                } else {
                    if stderr.is_empty() {
                        stdout
                    } else {
                        format!("{stdout}\n{stderr}")
                    }
                };
                if !o.status.success() && !output.is_empty() {
                    diagnostics.push(format!("[{name}]\n{output}"));
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::TimedOut => {
                diagnostics.push(format!("[{name}] timed out after {timeout}s"));
            }
            Err(_) => {
                diagnostics.push(format!("[{name}] runner not found"));
            }
        }
    }

    if !diagnostics.is_empty() {
        let msg = json!({"decision": "block", "reason": format!("Python lint errors detected:\n\n{}\n\nFix these issues.", diagnostics.join("\n\n"))});
        let _ = writeln!(io::stdout(), "{msg}");
    } else {
        save_cache(&current_hashes);
    }
}
