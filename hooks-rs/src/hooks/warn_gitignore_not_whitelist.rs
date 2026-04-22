use std::path::Path;

use crate::input::HookInput;
use crate::output::stop;

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if Path::new(file_path).file_name().and_then(|n| n.to_str()) != Some(".gitignore") {
        return;
    }
    let content = match std::fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => return,
    };

    for line in content.lines() {
        let stripped = line.trim();
        if stripped.is_empty() || stripped.starts_with('#') {
            continue;
        }
        if stripped.starts_with('*') {
            return;
        }
        break;
    }

    stop(
        ".gitignore が whitelist 形式ではありません。\n最初の実効行を `*` にして、`!pattern` で許可する形式にしてください。\n例:\n*\n!.gitignore\n!src/\n!src/**",
    );
}
