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
    for kw in BLOCKED_KEYWORDS {
        let re = Regex::new(&format!(r"(?i)\b{}\b", regex::escape(kw))).unwrap();
        if re.is_match(&commit_part) {
            block(&format!(
                "commit メッセージに '{kw}' を含めることは禁止されています。git add と git commit は別コマンドで実行してください。"
            ));
            return;
        }
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
        let kw = pattern
            .captures(&subject)
            .map(|c| c.get(1).unwrap().as_str().to_string())
            .or_else(|| {
                let full = std::process::Command::new("git")
                    .args(["log", "-1", "--format=%B", &hash])
                    .output()
                    .ok()?;
                let full_text = String::from_utf8_lossy(&full.stdout).to_string();
                Some(
                    pattern
                        .captures(&full_text)?
                        .get(1)
                        .unwrap()
                        .as_str()
                        .to_string(),
                )
            })
            .unwrap_or_else(|| "?".to_string());
        results.push((hash, subject, kw));
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
