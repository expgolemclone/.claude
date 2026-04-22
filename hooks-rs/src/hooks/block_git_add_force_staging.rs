use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }

    // 引用符内を除去してフラグ検出の誤検知を防ぐ
    let stripped = Regex::new(r#""[^"]*""#)
        .unwrap()
        .replace_all(command, r#""""#);
    let stripped = Regex::new(r"'[^']*'").unwrap().replace_all(&stripped, "''");

    let git_add_re = Regex::new(r"\bgit\s+add\b").unwrap();
    let force_re = Regex::new(r"\s(-f|--force)\b").unwrap();

    if git_add_re.is_match(&stripped) && force_re.is_match(&stripped) {
        block(
            "git add -f (--force) は禁止されています。.gitignore のルールを迂回する強制ステージングは許可されていません。",
        );
        return;
    }

    pass();
}
