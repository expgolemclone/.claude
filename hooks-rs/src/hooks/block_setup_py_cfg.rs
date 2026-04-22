use crate::input::HookInput;
use crate::output::{block, pass};

const PROHIBITED_NAMES: &[&str] = &["setup.py", "setup.cfg"];

fn prohibited_name_reason(file_path: &str) -> Option<String> {
    if file_path.is_empty() || file_path.contains(".claude") {
        return None;
    }

    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");

    if PROHIBITED_NAMES.contains(&basename) {
        return Some(format!(
            "{basename} は使用禁止です。pyproject.toml (PEP 621) を使用してください。"
        ));
    }

    None
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();

    if let Some(reason) = prohibited_name_reason(file_path) {
        block(&reason);
        return;
    }

    pass();
}

#[cfg(test)]
mod tests {
    use super::prohibited_name_reason;

    #[test]
    fn blocks_setup_py() {
        let reason = prohibited_name_reason("/tmp/project/setup.py").unwrap();
        assert!(reason.contains("setup.py"));
    }

    #[test]
    fn blocks_setup_cfg() {
        let reason = prohibited_name_reason("/tmp/project/setup.cfg").unwrap();
        assert!(reason.contains("setup.cfg"));
    }

    #[test]
    fn allows_similar_name() {
        assert_eq!(prohibited_name_reason("/tmp/project/test_setup.py"), None);
    }

    #[test]
    fn allows_claude_generator_setup_py() {
        assert_eq!(prohibited_name_reason("/home/user/.claude/setup.py"), None);
    }
}
