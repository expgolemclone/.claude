use crate::input::HookInput;
use crate::output::{block, pass};

const PROHIBITED_NAMES: &[&str] = &["setup.py", "setup.cfg"];

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    // Claude Code設定ジェネレーター（~/.claude/setup.py）は対象外
    if file_path.contains(".claude") {
        return;
    }

    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");

    if PROHIBITED_NAMES.contains(&basename) {
        block(&format!(
            "{basename} は使用禁止です。pyproject.toml (PEP 621) を使用してください。"
        ));
        return;
    }

    pass();
}
