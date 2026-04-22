use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }
    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");

    let content = match input.tool_name.as_str() {
        "Edit" => &input.tool_input.new_string,
        "Write" => &input.tool_input.content,
        _ => return,
    };
    if content.is_empty() {
        return;
    }

    let found = match basename {
        "pyproject.toml" => check_pyproject(content),
        "Cargo.toml" => check_cargo(content),
        "package.json" => check_package_json(content),
        _ => false,
    };

    if found {
        block(
            "バージョン上限のない依存指定は禁止です（config: upper_bound_required = true）。\n>= のみではなく、上限も指定してください（例: >=1.0,<2 / ~=1.0 / ^1.0）。",
        );
        return;
    }
    pass();
}

fn check_pyproject(content: &str) -> bool {
    let ge_re = Regex::new(r">=\s*[\d]").unwrap();
    for line in content.lines() {
        let stripped = line.trim();
        if stripped.starts_with('#') || stripped.contains("requires-python") {
            continue;
        }
        if stripped.contains(">=")
            && !stripped.contains('<')
            && !stripped.contains("~=")
            && ge_re.is_match(stripped)
        {
            return true;
        }
    }
    false
}

fn check_cargo(content: &str) -> bool {
    let wildcard_re = Regex::new(r#"['"](\s*\*\s*)['"]"#).unwrap();
    let ge_re = Regex::new(r">=\s*[\d]").unwrap();
    for line in content.lines() {
        let stripped = line.trim();
        if stripped.starts_with('#') {
            continue;
        }
        if wildcard_re.is_match(stripped) {
            return true;
        }
        if stripped.contains(">=") && !stripped.contains('<') && ge_re.is_match(stripped) {
            return true;
        }
    }
    false
}

fn check_package_json(content: &str) -> bool {
    let ge_re = Regex::new(r">=\s*[\d]").unwrap();
    for line in content.lines() {
        if line.contains(">=") && !line.contains('<') && ge_re.is_match(line) {
            return true;
        }
    }
    false
}
