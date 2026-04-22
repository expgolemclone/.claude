use std::path::Path;

use crate::input::HookInput;
use crate::output::block;

const BLOCKED_EXTENSIONS: &[&str] = &["sh", "bash", "js", "ts", "bat", "ps1", "rb", "pl"];

fn blocked_hook_extension(file_path: &str) -> Option<String> {
    let normalized = file_path.replace('\\', "/");
    if !normalized.contains("/.claude/hooks/") && !normalized.contains(".claude/hooks/") {
        return None;
    }
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    if BLOCKED_EXTENSIONS.contains(&ext.as_str()) {
        return Some(ext);
    }
    None
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    if let Some(ext) = blocked_hook_extension(file_path) {
        block(&format!(
            "hookスクリプトはPythonで作成してください（.{ext} は許可されていません）"
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::blocked_hook_extension;

    #[test]
    fn blocks_shell_script_inside_hooks_dir() {
        assert_eq!(
            blocked_hook_extension("/home/user/.claude/hooks/myhook.sh"),
            Some("sh".to_string())
        );
    }

    #[test]
    fn blocks_javascript_inside_hooks_dir() {
        assert_eq!(
            blocked_hook_extension("/home/user/.claude/hooks/myhook.js"),
            Some("js".to_string())
        );
    }

    #[test]
    fn allows_python_inside_hooks_dir() {
        assert_eq!(
            blocked_hook_extension("/home/user/.claude/hooks/myhook.py"),
            None
        );
    }

    #[test]
    fn allows_script_outside_hooks_dir() {
        assert_eq!(blocked_hook_extension("/tmp/project/script.sh"), None);
    }
}
