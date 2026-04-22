use regex::Regex;

use crate::input::HookInput;
use crate::output::block;

const BLOCKED_KEYWORDS: &[&str] = &[
    "authored",
    "claude",
    "anthropic",
    "ai",
    "llm",
    "gemini",
    "openai",
    "foundation",
    "copilot",
    "gpt",
    "chatgpt",
    "bard",
    "codeium",
    "cursor",
    "tabnine",
    "cody",
    "devin",
    "agent",
    "assistant",
    "エージェント",
];

fn contains_blocked_keyword(text: &str) -> Option<String> {
    for kw in BLOCKED_KEYWORDS {
        let re = Regex::new(&format!(r"(?i)\b{}\b", regex::escape(kw))).unwrap();
        if re.is_match(text) {
            return Some((*kw).to_string());
        }
    }
    None
}

fn parse_blocked_log_entries(stdout: &str) -> Vec<(String, String, String)> {
    let combined = BLOCKED_KEYWORDS
        .iter()
        .map(|kw| regex::escape(kw))
        .collect::<Vec<_>>()
        .join("|");
    let pattern = Regex::new(&format!(r"(?i)\b({combined})\b")).unwrap();
    let mut results: Vec<(String, String, String)> = Vec::new();
    let mut seen = std::collections::HashSet::new();

    for line in stdout.trim().lines() {
        let parts: Vec<&str> = line.splitn(2, ' ').collect();
        let hash = parts[0].to_string();
        if seen.contains(&hash) {
            continue;
        }
        seen.insert(hash.clone());
        let subject = parts.get(1).unwrap_or(&"").to_string();
        if let Some(caps) = pattern.captures(&subject) {
            let kw = caps.get(1).unwrap().as_str().to_string();
            results.push((hash, subject, kw));
        }
    }

    results
}

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }

    if Regex::new(r"\bgit\s+push\b").unwrap().is_match(command) {
        check_push();
        return;
    }

    if Regex::new(r"\bgit\s+commit\b").unwrap().is_match(command) {
        check_commit(command);
    }
}

fn check_commit(command: &str) {
    let commit_part = extract_commit_portion(command);
    if commit_part.is_empty() {
        return;
    }
    if let Some(kw) = contains_blocked_keyword(&commit_part) {
        block(&format!(
            "commit メッセージに '{kw}' を含めることは禁止されています。git add と git commit は別コマンドで実行してください。"
        ));
    }
}

fn extract_commit_portion(command: &str) -> String {
    match Regex::new(r"\bgit\s+commit\b").unwrap().find(command) {
        Some(m) => command[m.start()..].to_string(),
        None => String::new(),
    }
}

fn check_push() {
    let output = std::process::Command::new("git")
        .args(["rev-parse", "--abbrev-ref", "@{upstream}"])
        .output();
    let has_upstream = output.map(|o| o.status.success()).unwrap_or(false);

    let rev_range = if has_upstream {
        vec!["@{upstream}..HEAD"]
    } else {
        vec!["--all"]
    };

    let combined = BLOCKED_KEYWORDS
        .iter()
        .map(|kw| regex::escape(kw))
        .collect::<Vec<_>>()
        .join("|");

    let output = std::process::Command::new("git")
        .args(["log"])
        .args(&rev_range)
        .arg(format!("--grep=\\b({combined})\\b"))
        .args(["-i", "-P", "--format=%h %s"])
        .output();

    let stdout = match output {
        Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).to_string(),
        _ => return,
    };

    if stdout.trim().is_empty() {
        return;
    }

    let mut results = parse_blocked_log_entries(&stdout);
    let pattern = Regex::new(&format!(r"(?i)\b({combined})\b")).unwrap();
    for (hash, subject, kw) in &mut results {
        if kw != "?" || pattern.is_match(subject) {
            continue;
        }
        if let Ok(full) = std::process::Command::new("git")
            .args(["log", "-1", "--format=%B", hash])
            .output()
        {
            let full_text = String::from_utf8_lossy(&full.stdout).to_string();
            if let Some(caps) = pattern.captures(&full_text) {
                *kw = caps.get(1).unwrap().as_str().to_string();
            }
        }
    }

    if results.is_empty() {
        return;
    }

    let lines: Vec<String> = results
        .iter()
        .map(|(h, s, kw)| format!("  {h} {s} (keyword: {kw})"))
        .collect();
    block(&format!(
        "git log に禁止キーワードを含むコミットが見つかりました:\n{}\ngit rebase -i で該当コミットのメッセージを修正してください。",
        lines.join("\n")
    ));
}

#[cfg(test)]
mod tests {
    use super::{contains_blocked_keyword, extract_commit_portion, parse_blocked_log_entries};

    #[test]
    fn detects_blocked_keyword_in_commit_message() {
        assert_eq!(
            contains_blocked_keyword("fix: claude integration"),
            Some("claude".to_string())
        );
    }

    #[test]
    fn keyword_matching_is_case_insensitive() {
        assert_eq!(
            contains_blocked_keyword("Generated with Claude Code"),
            Some("claude".to_string())
        );
    }

    #[test]
    fn word_boundary_avoids_false_positive() {
        assert_eq!(
            contains_blocked_keyword("feat: add wait logic for retries"),
            None
        );
    }

    #[test]
    fn extracts_commit_portion_after_prefix_command() {
        assert_eq!(
            extract_commit_portion(r#"cd repo && git commit -m "fix""#),
            r#"git commit -m "fix""#
        );
    }

    #[test]
    fn parses_blocked_log_entries() {
        let entries = parse_blocked_log_entries("abc123 feat: add claude integration\n");
        assert_eq!(
            entries,
            vec![(
                "abc123".to_string(),
                "feat: add claude integration".to_string(),
                "claude".to_string()
            )]
        );
    }

    #[test]
    fn parse_log_entries_deduplicates_hashes() {
        let entries = parse_blocked_log_entries(
            "abc123 feat: add claude integration\nabc123 feat: add claude integration\n",
        );
        assert_eq!(entries.len(), 1);
    }
}
