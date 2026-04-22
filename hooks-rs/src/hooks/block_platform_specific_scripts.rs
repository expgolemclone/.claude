use regex::Regex;

use crate::input::HookInput;
use crate::output::{block, pass};

const UNIX_ONLY: &[&str] = &[".sh", ".bash", ".zsh", ".csh", ".tcsh", ".fish", ".ksh"];
const WINDOWS_ONLY: &[&str] = &[
    ".ps1", ".psm1", ".psd1", ".bat", ".cmd", ".vbs", ".vbe", ".wsf", ".wsh",
];

fn classify(ext: &str) -> Option<&'static str> {
    if UNIX_ONLY.contains(&ext) {
        return Some("Unix");
    }
    if WINDOWS_ONLY.contains(&ext) {
        return Some("Windows");
    }
    None
}

fn ext_reason(ext: &str) -> Option<String> {
    match classify(ext)? {
        "Unix" => Some(format!(
            "それはWindowsでは使えません。.pyにしてください。（{ext}）"
        )),
        _ => Some(format!(
            "それはLinuxでは使えません。.pyにしてください。（{ext}）"
        )),
    }
}

fn reason_for_path(file_path: &str) -> Option<String> {
    let ext = std::path::Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");
    let ext_lower = format!(".{ext}").to_lowercase();
    ext_reason(&ext_lower)
}

fn reason_for_command(command: &str) -> Option<String> {
    let redirect_re = Regex::new(r#">{1,2}\s*["']?(\S+?)["']?\s*$"#).unwrap();
    let touch_re = Regex::new(r#"\btouch\s+(?:-\S+\s+)*["']?(\S+?)["']?\s*$"#).unwrap();
    let tee_re = Regex::new(r#"\btee\s+(?:-\S+\s+)*["']?(\S+?)["']?\s*$"#).unwrap();

    for re in [&redirect_re, &touch_re, &tee_re] {
        if let Some(caps) = re.captures(command)
            && let Some(m) = caps.get(1)
            && let Some(reason) = reason_for_path(m.as_str()) {
                return Some(reason);
            }
    }

    None
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.is_empty()
        && let Some(reason) = reason_for_path(file_path) {
            block(&reason);
            return;
        }

    let command = &input.tool_input.command;
    if !command.is_empty()
        && let Some(reason) = reason_for_command(command) {
            block(&reason);
            return;
        }

    pass();
}

#[cfg(test)]
mod tests {
    use super::{reason_for_command, reason_for_path};

    #[test]
    fn unix_extension_is_blocked_for_path() {
        let reason = reason_for_path("/tmp/project/script.sh").unwrap();
        assert!(reason.contains("Windows"));
    }

    #[test]
    fn windows_extension_is_blocked_for_path() {
        let reason = reason_for_path("C:/scripts/script.bat").unwrap();
        assert!(reason.contains("Linux"));
    }

    #[test]
    fn python_file_path_is_allowed() {
        assert_eq!(reason_for_path("/tmp/script.py"), None);
    }

    #[test]
    fn redirect_command_detects_platform_specific_file() {
        let reason = reason_for_command("echo '#!/bin/bash' > deploy.sh").unwrap();
        assert!(reason.contains("Windows"));
    }

    #[test]
    fn read_only_command_is_allowed() {
        assert_eq!(reason_for_command("cat deploy.sh"), None);
    }
}
