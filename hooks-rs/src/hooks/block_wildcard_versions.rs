use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

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

    let re = Regex::new(r#"['"](\s*\*\s*)['"]"#).unwrap();
    if re.is_match(content) {
        block(
            "ワイルドカードバージョン（\"*\"）は禁止です。具体的なバージョン範囲を指定してください。",
        );
        return;
    }

    pass();
}
