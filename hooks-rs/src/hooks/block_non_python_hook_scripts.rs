use std::path::Path;

use crate::input::HookInput;
use crate::output::block;

const BLOCKED_EXTENSIONS: &[&str] = &["sh", "bash", "js", "ts", "bat", "ps1", "rb", "pl"];

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }
    let normalized = file_path.replace('\\', "/");
    if !normalized.contains("/.claude/hooks/") && !normalized.contains(".claude/hooks/") {
        return;
    }
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    if BLOCKED_EXTENSIONS.contains(&ext.as_str()) {
        block(&format!(
            "hookスクリプトはPythonで作成してください（.{ext} は許可されていません）"
        ));
    }
}
