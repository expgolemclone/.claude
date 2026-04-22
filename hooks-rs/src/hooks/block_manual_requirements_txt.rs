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

    let re = Regex::new(r"(?i)^requirements.*\.txt$").unwrap();
    if re.is_match(basename) {
        block("requirements.txt の手書き編集は禁止です。uv pip compile で生成してください。");
        return;
    }

    pass();
}
