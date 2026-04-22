use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

fn is_manual_requirements_file(file_path: &str) -> bool {
    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");

    Regex::new(r"(?i)^requirements.*\.txt$")
        .unwrap()
        .is_match(basename)
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    if is_manual_requirements_file(file_path) {
        block("requirements.txt の手書き編集は禁止です。uv pip compile で生成してください。");
        return;
    }

    pass();
}

#[cfg(test)]
mod tests {
    use super::is_manual_requirements_file;

    #[test]
    fn detects_requirements_txt() {
        assert!(is_manual_requirements_file("/tmp/project/requirements.txt"));
    }

    #[test]
    fn detects_nested_requirements_txt() {
        assert!(is_manual_requirements_file(
            "/home/user/app/requirements-dev.txt"
        ));
    }

    #[test]
    fn ignores_requirements_in() {
        assert!(!is_manual_requirements_file("/tmp/project/requirements.in"));
    }

    #[test]
    fn ignores_unrelated_text_file() {
        assert!(!is_manual_requirements_file("/tmp/project/notes.txt"));
    }
}
