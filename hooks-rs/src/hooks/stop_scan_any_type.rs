use regex::Regex;

use crate::git::git_tracked_py_files;
use crate::input::HookInput;
use crate::output::block;

fn file_uses_any_type(text: &str) -> bool {
    let py_import_re = Regex::new(r"from\s+typing\b.*\bAny\b").unwrap();
    let py_qualified_re = Regex::new(r"\btyping\.Any\b").unwrap();
    let py_bare_re = Regex::new(r"\bAny\b").unwrap();
    let comment_re = Regex::new(r"^\s*#").unwrap();
    let string_re = Regex::new(r#""(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'"#).unwrap();

    for line in text.lines() {
        if comment_re.is_match(line) {
            continue;
        }
        let stripped = string_re.replace_all(line, "\"\"");
        if py_import_re.is_match(&stripped)
            || py_qualified_re.is_match(&stripped)
            || py_bare_re.is_match(&stripped)
        {
            return true;
        }
    }
    false
}

fn collect_violations(root: &std::path::Path) -> Vec<String> {
    let mut violations: Vec<String> = Vec::new();
    for py_file in git_tracked_py_files(root) {
        let text = match std::fs::read_to_string(&py_file) {
            Ok(t) => t,
            Err(_) => continue,
        };
        if file_uses_any_type(&text) {
            violations.push(format!("{}", py_file.display()));
        }
    }
    violations
}

pub fn run(input: &HookInput) {
    if input.permission_mode == "plan" {
        return;
    }
    let cwd = &input.cwd;
    if cwd.is_empty() {
        return;
    }

    let violations = collect_violations(std::path::Path::new(cwd));

    if !violations.is_empty() {
        let file_list = violations
            .iter()
            .map(|v| format!("  - {v}"))
            .collect::<Vec<_>>()
            .join("\n");
        block(&format!(
            "Any 型が {} 個のファイルに残っています:\n{file_list}\n\n具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。",
            violations.len()
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::file_uses_any_type;

    #[test]
    fn detects_any_type_usage() {
        assert!(file_uses_any_type("from typing import Any\nx: Any = 1\n"));
    }

    #[test]
    fn ignores_comment_only_any() {
        assert!(!file_uses_any_type("# Any type here\nx: int = 1\n"));
    }

    #[test]
    fn ignores_clean_python_file() {
        assert!(!file_uses_any_type("x: int = 1\n"));
    }

    #[test]
    fn collect_violations_detects_any_in_tracked_file() {
        use std::process::Command;
        use tempfile::TempDir;

        let repo = TempDir::new().unwrap();
        let root = repo.path();

        Command::new("git")
            .args(["init"])
            .current_dir(root)
            .output()
            .unwrap();
        Command::new("git")
            .args(["config", "user.email", "test@example.com"])
            .current_dir(root)
            .output()
            .unwrap();
        Command::new("git")
            .args(["config", "user.name", "Test"])
            .current_dir(root)
            .output()
            .unwrap();

        let clean = root.join("clean.py");
        std::fs::write(&clean, "x: int = 1\n").unwrap();
        let dirty = root.join("dirty.py");
        std::fs::write(&dirty, "from typing import Any\ny: Any = 1\n").unwrap();

        Command::new("git")
            .args(["add", "."])
            .current_dir(root)
            .output()
            .unwrap();
        Command::new("git")
            .args(["commit", "-m", "init"])
            .current_dir(root)
            .output()
            .unwrap();

        let violations = super::collect_violations(root);
        assert_eq!(violations.len(), 1);
        assert!(violations[0].contains("dirty.py"));
    }
}
