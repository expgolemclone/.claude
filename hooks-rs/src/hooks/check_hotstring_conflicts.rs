use regex::Regex;
use serde_json::json;
use std::io::{self, Write};

use crate::input::HookInput;

const EXCLUDE_DIRS: &[&str] = &[".tools", ".git", ".log"];

type Hotstring = (String, String, usize);
type HotstringConflict = (Hotstring, Hotstring);

fn ahk_project_dir() -> std::path::PathBuf {
    home::home_dir()
        .unwrap_or_default()
        .join("Documents")
        .join("AutoHotkey")
}

fn find_ahk_files(root: &std::path::Path) -> Vec<std::path::PathBuf> {
    let mut files = Vec::new();
    find_ahk_recursive(root, root, &mut files);
    files
}

fn find_ahk_recursive(
    dir: &std::path::Path,
    root: &std::path::Path,
    files: &mut Vec<std::path::PathBuf>,
) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if let Ok(rel) = path.strip_prefix(root)
                && rel
                    .components()
                    .any(|c| EXCLUDE_DIRS.contains(&c.as_os_str().to_str().unwrap_or("")))
            {
                continue;
            }
            find_ahk_recursive(&path, root, files);
        } else if path.extension().and_then(|e| e.to_str()) == Some("ahk") {
            files.push(path);
        }
    }
}

fn extract_hotstrings(file_path: &std::path::Path) -> Vec<(String, String, usize)> {
    let re = Regex::new(r"^:([^:]*):(.+?)::").unwrap();
    let content = match std::fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };
    let mut results = Vec::new();
    for (i, line) in content.lines().enumerate() {
        if let Some(caps) = re.captures(line.trim())
            && let Some(trigger) = caps.get(2)
        {
            results.push((
                trigger.as_str().to_string(),
                file_path.display().to_string(),
                i + 1,
            ));
        }
    }
    results
}

fn find_prefix_conflicts(hotstrings: &[Hotstring]) -> Vec<HotstringConflict> {
    let mut conflicts = Vec::new();
    for i in 0..hotstrings.len() {
        for j in (i + 1)..hotstrings.len() {
            let (ta, _, _) = &hotstrings[i];
            let (tb, _, _) = &hotstrings[j];
            if ta != tb {
                if tb.starts_with(ta.as_str()) {
                    conflicts.push((hotstrings[i].clone(), hotstrings[j].clone()));
                } else if ta.starts_with(tb.as_str()) {
                    conflicts.push((hotstrings[j].clone(), hotstrings[i].clone()));
                }
            }
        }
    }
    conflicts
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with(".ahk") {
        return;
    }

    let project_dir = ahk_project_dir();
    if std::path::Path::new(file_path)
        .strip_prefix(&project_dir)
        .is_err()
    {
        return;
    }

    let mut all_hotstrings = Vec::new();
    for f in find_ahk_files(&project_dir) {
        all_hotstrings.extend(extract_hotstrings(&f));
    }

    let conflicts = find_prefix_conflicts(&all_hotstrings);
    if conflicts.is_empty() {
        return;
    }

    let lines: Vec<String> = conflicts
        .iter()
        .map(|((st, sf, sl), (lt, lf, ll))| {
            let sr = std::path::Path::new(sf)
                .strip_prefix(&project_dir)
                .unwrap_or(std::path::Path::new(sf))
                .display();
            let lr = std::path::Path::new(lf)
                .strip_prefix(&project_dir)
                .unwrap_or(std::path::Path::new(lf))
                .display();
            format!("  '{st}' ({sr}:{sl}) は '{lt}' ({lr}:{ll}) のプレフィックスです")
        })
        .collect();

    let msg = json!({"decision": "block", "reason": format!(
        "ホットストリングのプレフィックス競合が検出されました:\n{}", lines.join("\n")
    )});
    let _ = writeln!(io::stdout(), "{msg}");
}

#[cfg(test)]
mod tests {
    use super::{extract_hotstrings, find_ahk_files, find_prefix_conflicts};
    use tempfile::tempdir;

    #[test]
    fn extracts_simple_hotstring() {
        let dir = tempdir().unwrap();
        let file = dir.path().join("test.ahk");
        std::fs::write(&file, "::btw::by the way\n").unwrap();

        let result = extract_hotstrings(&file);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "btw");
        assert_eq!(result[0].2, 1);
    }

    #[test]
    fn returns_empty_for_non_hotstring_file() {
        let dir = tempdir().unwrap();
        let file = dir.path().join("test.ahk");
        std::fs::write(&file, "; just a comment\nMsgBox Hello\n").unwrap();

        assert!(extract_hotstrings(&file).is_empty());
    }

    #[test]
    fn detects_prefix_conflict() {
        let conflicts = find_prefix_conflicts(&[
            ("ab".to_string(), "f1".to_string(), 1),
            ("abc".to_string(), "f1".to_string(), 2),
        ]);

        assert_eq!(conflicts.len(), 1);
        assert_eq!(conflicts[0].0.0, "ab");
        assert_eq!(conflicts[0].1.0, "abc");
    }

    #[test]
    fn identical_triggers_do_not_conflict() {
        let conflicts = find_prefix_conflicts(&[
            ("abc".to_string(), "f1".to_string(), 1),
            ("abc".to_string(), "f2".to_string(), 2),
        ]);

        assert!(conflicts.is_empty());
    }

    #[test]
    fn skips_excluded_directories_when_listing_files() {
        let dir = tempdir().unwrap();
        std::fs::create_dir(dir.path().join(".git")).unwrap();
        std::fs::write(dir.path().join(".git").join("hidden.ahk"), "").unwrap();
        std::fs::write(dir.path().join("visible.ahk"), "").unwrap();

        let result = find_ahk_files(dir.path());
        assert_eq!(result.len(), 1);
        assert!(result[0].ends_with("visible.ahk"));
    }
}
