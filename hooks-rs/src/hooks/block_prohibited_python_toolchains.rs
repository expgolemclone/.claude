use regex::Regex;

use crate::git::strip_quotes;
use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }
    let stripped = strip_quotes(command);
    let boundary = r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)";
    let sudo = r"(?:sudo\s+)?";

    let prohibited_re =
        Regex::new(&format!("{boundary}{sudo}(pyenv|conda|pipenv|poetry)\\b")).unwrap();
    if let Some(caps) = prohibited_re.captures(&stripped) {
        let tool = caps.get(1).unwrap().as_str();
        block(&format!(
            "{tool} は使用禁止です。代わりに uv を使用してください。"
        ));
        return;
    }

    let pip_re = Regex::new(&format!("{boundary}{sudo}pip3?\\b")).unwrap();
    if pip_re.is_match(&stripped) {
        block("pip の直接使用は禁止です。代わりに uv pip を使用してください。");
        return;
    }

    pass();
}
