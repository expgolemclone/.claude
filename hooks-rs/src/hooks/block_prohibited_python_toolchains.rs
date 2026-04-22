use regex::Regex;

use crate::git::strip_quotes;
use crate::input::HookInput;
use crate::output::{block, pass};

fn blocked_reason(command: &str) -> Option<String> {
    let stripped = strip_quotes(command);
    let boundary = r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)";
    let sudo = r"(?:sudo\s+)?";

    let prohibited_re =
        Regex::new(&format!("{boundary}{sudo}(pyenv|conda|pipenv|poetry)\\b")).unwrap();
    if let Some(caps) = prohibited_re.captures(&stripped) {
        let tool = caps.get(1).unwrap().as_str();
        return Some(format!(
            "{tool} は使用禁止です。代わりに uv を使用してください。"
        ));
    }

    let pip_re = Regex::new(&format!("{boundary}{sudo}pip3?\\b")).unwrap();
    if pip_re.is_match(&stripped) {
        return Some("pip の直接使用は禁止です。代わりに uv pip を使用してください。".to_string());
    }

    None
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }

    if let Some(reason) = blocked_reason(command) {
        block(&reason);
        return;
    }

    pass();
}

#[cfg(test)]
mod tests {
    use super::blocked_reason;

    #[test]
    fn blocks_direct_conda_command() {
        let reason = blocked_reason("conda install numpy").unwrap();
        assert!(reason.contains("conda"));
    }

    #[test]
    fn blocks_prohibited_tool_after_separator() {
        assert!(blocked_reason("echo hello; poetry add flask").is_some());
    }

    #[test]
    fn blocks_direct_pip_usage() {
        let reason = blocked_reason("pip install numpy").unwrap();
        assert!(reason.contains("uv pip"));
    }

    #[test]
    fn allows_uv_pip_install() {
        assert_eq!(blocked_reason("uv pip install numpy"), None);
    }

    #[test]
    fn ignores_tool_name_inside_quotes() {
        assert_eq!(blocked_reason(r#"echo "use conda instead""#), None);
    }
}
