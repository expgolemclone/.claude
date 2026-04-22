use regex::Regex;

use crate::git::git_tracked_py_files;
use crate::input::HookInput;
use crate::output::block;

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }
    let cwd = &input.cwd;
    if cwd.is_empty() {
        return;
    }

    let py_import_re = Regex::new(r"from\s+typing\b.*\bAny\b").unwrap();
    let py_qualified_re = Regex::new(r"\btyping\.Any\b").unwrap();
    let py_bare_re = Regex::new(r"\bAny\b").unwrap();
    let comment_re = Regex::new(r"^\s*#").unwrap();
    let string_re = Regex::new(r#""(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'"#).unwrap();

    let root = std::path::Path::new(cwd);
    let mut violations: Vec<String> = Vec::new();

    for py_file in git_tracked_py_files(root) {
        let text = match std::fs::read_to_string(&py_file) {
            Ok(t) => t,
            Err(_) => continue,
        };
        for line in text.lines() {
            if comment_re.is_match(line) {
                continue;
            }
            let stripped = string_re.replace_all(line, "\"\"");
            if py_import_re.is_match(&stripped)
                || py_qualified_re.is_match(&stripped)
                || py_bare_re.is_match(&stripped)
            {
                violations.push(format!("{}", py_file.display()));
                break;
            }
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
