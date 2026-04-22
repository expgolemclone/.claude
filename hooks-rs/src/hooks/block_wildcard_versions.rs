use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

fn contains_wildcard_version(content: &str) -> bool {
    Regex::new(r#"['"](\s*\*\s*)['"]"#)
        .unwrap()
        .is_match(content)
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() || !file_path.ends_with("pyproject.toml") {
        return;
    }

    let content = match input.tool_name.as_str() {
        "Edit" => &input.tool_input.new_string,
        "Write" => &input.tool_input.content,
        _ => return,
    };

    if content.is_empty() {
        return;
    }

    if contains_wildcard_version(content) {
        block(
            "ワイルドカードバージョン（\"*\"）は禁止です。具体的なバージョン範囲を指定してください。",
        );
        return;
    }

    pass();
}

#[cfg(test)]
mod tests {
    use super::contains_wildcard_version;

    #[test]
    fn detects_double_quoted_wildcard() {
        assert!(contains_wildcard_version(r#"version = "*""#));
    }

    #[test]
    fn detects_single_quoted_wildcard() {
        assert!(contains_wildcard_version("version = '*'"));
    }

    #[test]
    fn ignores_specific_version_range() {
        assert!(!contains_wildcard_version(r#"version = ">=1.0,<2.0""#));
    }

    #[test]
    fn ignores_glob_pattern() {
        assert!(!contains_wildcard_version(r#"include = ["*.py"]"#));
    }
}
