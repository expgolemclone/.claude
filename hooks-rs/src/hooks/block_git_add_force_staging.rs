use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

fn is_forced_git_add(command: &str) -> bool {
    let stripped = Regex::new(r#""[^"]*""#)
        .unwrap()
        .replace_all(command, r#""""#);
    let stripped = Regex::new(r"'[^']*'").unwrap().replace_all(&stripped, "''");

    let git_add_re = Regex::new(r"\bgit\s+add\b").unwrap();
    let force_re = Regex::new(r"\s(-f|--force)\b").unwrap();

    git_add_re.is_match(&stripped) && force_re.is_match(&stripped)
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }

    if is_forced_git_add(command) {
        block(
            "git add -f (--force) は禁止されています。.gitignore のルールを迂回する強制ステージングは許可されていません。",
        );
        return;
    }

    pass();
}

#[cfg(test)]
mod tests {
    use super::is_forced_git_add;

    #[test]
    fn detects_short_force_flag() {
        assert!(is_forced_git_add("git add -f ."));
    }

    #[test]
    fn detects_long_force_flag() {
        assert!(is_forced_git_add("git add --force somefile.txt"));
    }

    #[test]
    fn ignores_normal_git_add() {
        assert!(!is_forced_git_add("git add ."));
    }

    #[test]
    fn ignores_force_inside_quotes() {
        assert!(!is_forced_git_add(r#"git commit -m "add -f feature flag""#));
    }
}
