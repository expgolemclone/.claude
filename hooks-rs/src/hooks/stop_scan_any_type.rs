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

pub fn run(input: &HookInput) {
    if input.permission_mode == "plan" {
        return;
    }
    let cwd = &input.cwd;
    if cwd.is_empty() {
        return;
    }

    let root = std::path::Path::new(cwd);
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
}
