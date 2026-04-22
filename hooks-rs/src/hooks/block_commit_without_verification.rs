use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::path::Path;

use crate::input::HookInput;
use crate::output::block;
use crate::transcript;

const CODE_EXTENSIONS: &[&str] = &[".py", ".go", ".rs", ".c", ".cpp", ".cc"];
const SKIP_DIR_NAMES: &[&str] = &["hooks"];

fn is_code_execution(cmd: &str) -> bool {
    let exclude: Vec<Regex> = [
        r"\buv\s+run\s+python3?\s+-c\b",
        r"\buv\s+run\s+python3?\s+-m\s+(pytest|unittest)\b",
        r"\./?(true|false|echo)\b",
    ]
    .iter()
    .filter_map(|p| Regex::new(p).ok())
    .collect();
    if exclude.iter().any(|re| re.is_match(cmd)) {
        return false;
    }
    let exec_patterns: Vec<Regex> = [
        r"\buv\s+run\s+python3?\b",
        r"\bgo\s+run\b",
        r"\bgo\s+build\b",
        r"\bcargo\s+run\b",
        r"\./\w[\w./-]*",
    ]
    .iter()
    .filter_map(|p| Regex::new(p).ok())
    .collect();
    exec_patterns.iter().any(|re| re.is_match(cmd))
}

fn has_main_block(file_path: &str) -> bool {
    let content = match std::fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => return false,
    };
    Regex::new(r#"if\s+__name__\s*[=!]+\s*['"]__main__['"]"#)
        .map(|re| re.is_match(&content))
        .unwrap_or(false)
}

fn is_test_file(file_path: &str) -> bool {
    let basename = Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");
    basename.starts_with("test_")
        || basename.ends_with("_test.py")
        || basename.ends_with("_test.go")
        || (basename.starts_with("test_") && [".c", ".cpp", ".cc"].contains(&ext))
}

fn is_test_execution(cmd: &str) -> bool {
    let patterns: Vec<Regex> = [
        r"\buv\s+run\s+(pytest|py\.test)\b",
        r"\buv\s+run\s+.*-m\s+(pytest|unittest)\b",
        r"\bgo\s+test\b",
        r"\bcargo\s+test\b",
    ]
    .iter()
    .filter_map(|p| Regex::new(p).ok())
    .collect();
    patterns.iter().any(|re| re.is_match(cmd))
}

fn cmd_references_file(cmd: &str, file_path: &str) -> bool {
    if cmd.contains(file_path) {
        return true;
    }
    let fp_normalized = file_path.replace('\\', "/");
    let basename = fp_normalized.rsplit('/').next().unwrap_or("");
    if !basename.is_empty() {
        let pattern = Regex::new(&format!(
            r#"(?:^|\s|["'/])({})(?:\s|["'/]|$)"#,
            regex::escape(basename)
        ));
        if let Ok(re) = pattern
            && re.is_match(cmd)
        {
            return true;
        }
    }
    if file_path.ends_with(".go") && cmd.contains("./...") {
        return true;
    }
    false
}

fn looks_like_git_commit(command: &str) -> bool {
    let cmd = command.replace("\\\n", " ");
    Regex::new(r"\bgit\s+commit\b")
        .map(|re| re.is_match(&cmd))
        .unwrap_or(false)
        || Regex::new(r"\bgit\s+\$")
            .map(|re| re.is_match(&cmd))
            .unwrap_or(false)
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if !looks_like_git_commit(command) {
        return;
    }

    let transcript_path = &input.transcript_path;
    if transcript_path.is_empty() {
        block("transcript_path not available for verification");
        return;
    }

    let entries = match transcript::read_transcript_checked(Path::new(transcript_path)) {
        Ok(entries) => entries,
        Err(_) => {
            block("Cannot read transcript for verification");
            return;
        }
    };

    let mut edited_files: HashMap<String, usize> = HashMap::new();
    let mut verified: HashSet<String> = HashSet::new();
    let mut seq: usize = 0;

    for entry in &entries {
        let content = match entry
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_array())
        {
            Some(a) => a,
            None => continue,
        };

        for blk in content {
            if blk.get("type").and_then(|t| t.as_str()) != Some("tool_use") {
                continue;
            }
            let name = blk.get("name").and_then(|n| n.as_str()).unwrap_or("");
            let inp = blk.get("input").cloned().unwrap_or_default();

            if name == "Edit" || name == "Write" {
                let fp = inp
                    .get("file_path")
                    .or_else(|| inp.get("path"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                if fp.is_empty() {
                    continue;
                }
                let ext = Path::new(&fp)
                    .extension()
                    .and_then(|e| e.to_str())
                    .map(|e| format!(".{e}"))
                    .unwrap_or_default();
                if !CODE_EXTENSIONS.contains(&ext.as_str()) {
                    continue;
                }
                let fp_norm = fp.replace('\\', "/");
                let path_parts: HashSet<&str> = fp_norm.split('/').collect();
                if SKIP_DIR_NAMES.iter().any(|d| path_parts.contains(d)) {
                    continue;
                }
                if has_main_block(&fp) || is_test_file(&fp) {
                    edited_files.insert(fp, seq);
                }
            } else if name == "Bash" {
                let cmd = inp
                    .get("command")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                if is_code_execution(&cmd) {
                    for (fp, edit_seq) in &edited_files {
                        if *edit_seq < seq && cmd_references_file(&cmd, fp) {
                            verified.insert(fp.clone());
                        }
                    }
                } else if is_test_execution(&cmd) {
                    for (fp, edit_seq) in &edited_files {
                        if *edit_seq < seq && is_test_file(fp) && cmd_references_file(&cmd, fp) {
                            verified.insert(fp.clone());
                        }
                    }
                }
            }
        }
        seq += 1;
    }

    let unverified: Vec<&String> = edited_files
        .keys()
        .filter(|f| !verified.contains(*f))
        .collect();
    if unverified.is_empty() {
        return;
    }

    let listing: Vec<String> = unverified.iter().map(|fp| format!("  - {fp}")).collect();
    block(&format!(
        "以下のファイルがまだ実行されていません。コミット前に実行してください:\n{}\n\n\
         ソースファイルは直接実行（例: uv run python <file>）、\
         テストファイルはテスト実行（例: uv run pytest <file>）で検証してください。\n\
         上記のフルパスをそのまま指定できます。",
        listing.join("\n")
    ));
}
