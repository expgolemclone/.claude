use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }
    let ext = std::path::Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");

    let checker = match ext {
        "py" => check_python as fn(&str) -> bool,
        "go" => check_go as fn(&str) -> bool,
        "rs" => check_rust as fn(&str) -> bool,
        _ => return,
    };

    let content = match input.tool_name.as_str() {
        "Edit" => &input.tool_input.new_string,
        "Write" => &input.tool_input.content,
        _ => return,
    };

    if content.is_empty() {
        return;
    }

    if checker(content) {
        let suggestion = match ext {
            "py" => "具体的な型、Protocol、TypeVar、またはジェネリクスで置き換えてください。",
            "go" => {
                "ジェネリクス（型パラメータ）または具体的なインターフェースで置き換えてください。"
            }
            "rs" => "具体的なトレイト境界またはジェネリクスで置き換えてください。",
            _ => "",
        };
        block(&format!(
            "Any 型の使用は禁止されています（config: no_any = true）。\n{suggestion}"
        ));
        return;
    }
    pass();
}

fn check_python(text: &str) -> bool {
    let comment_re = Regex::new(r"^\s*#").unwrap();
    let string_re = Regex::new(r#""(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'"#).unwrap();
    let import_any_re = Regex::new(r"from\s+typing\b.*\bAny\b").unwrap();
    let qualified_re = Regex::new(r"\btyping\.Any\b").unwrap();
    let bare_re = Regex::new(r"\bAny\b").unwrap();

    for line in text.lines() {
        if comment_re.is_match(line) {
            continue;
        }
        let stripped = string_re.replace_all(line, "\"\"");
        if import_any_re.is_match(&stripped) {
            return true;
        }
        if qualified_re.is_match(&stripped) {
            return true;
        }
        if bare_re.is_match(&stripped) {
            return true;
        }
    }
    false
}

fn check_go(text: &str) -> bool {
    let comment_re = Regex::new(r"^\s*//").unwrap();
    let import_re = Regex::new(r"^\s*import\s").unwrap();
    let interface_re = Regex::new(r"\binterface\s*\{\s*\}").unwrap();
    let any_re = Regex::new(r"\bany\b").unwrap();
    let string_re = Regex::new(r#""(?:[^"\\]|\\.)*"|`[^`]*`"#).unwrap();

    for line in text.lines() {
        if comment_re.is_match(line) || import_re.is_match(line) {
            continue;
        }
        let stripped = string_re.replace_all(line, "\"\"");
        if interface_re.is_match(&stripped) {
            return true;
        }
        if any_re.is_match(&stripped) {
            return true;
        }
    }
    false
}

fn check_rust(text: &str) -> bool {
    let comment_re = Regex::new(r"^\s*//").unwrap();
    let string_re = Regex::new(r#""(?:[^"\\]|\\.)*""#).unwrap();
    let use_re = Regex::new(r"\buse\s+std::any::Any\b").unwrap();
    let dyn_re = Regex::new(r"\bdyn\s+Any\b").unwrap();

    for line in text.lines() {
        if comment_re.is_match(line) {
            continue;
        }
        let stripped = string_re.replace_all(line, "\"\"");
        if use_re.is_match(&stripped) {
            return true;
        }
        if dyn_re.is_match(&stripped) {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::{check_go, check_python, check_rust};

    #[test]
    fn python_any_import_is_detected() {
        assert!(check_python("from typing import Any\nx: Any = 1\n"));
    }

    #[test]
    fn python_comment_only_is_ignored() {
        assert!(!check_python("# This uses Any\nx: int = 1\n"));
    }

    #[test]
    fn go_any_is_detected() {
        assert!(check_go("var x any\n"));
    }

    #[test]
    fn rust_dyn_any_is_detected() {
        assert!(check_rust("let x: Box<dyn Any> = todo!();\n"));
    }
}
