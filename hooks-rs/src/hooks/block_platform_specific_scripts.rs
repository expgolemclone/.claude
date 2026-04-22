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

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.is_empty() {
        let ext = std::path::Path::new(file_path)
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("");
        let ext_lower = format!(".{ext}").to_lowercase();
        if let Some(reason) = ext_reason(&ext_lower) {
            block(&reason);
            return;
        }
    }

    let command = &input.tool_input.command;
    if !command.is_empty() {
        let redirect_re = Regex::new(r#">{1,2}\s*["']?(\S+?)["']?\s*$"#).unwrap();
        let touch_re = Regex::new(r#"\btouch\s+(?:-\S+\s+)*["']?(\S+?)["']?\s*$"#).unwrap();
        let tee_re = Regex::new(r#"\btee\s+(?:-\S+\s+)*["']?(\S+?)["']?\s*$"#).unwrap();

        for re in [&redirect_re, &touch_re, &tee_re] {
            if let Some(caps) = re.captures(command)
                && let Some(m) = caps.get(1)
            {
                let filepath = m.as_str();
                let ext = std::path::Path::new(filepath)
                    .extension()
                    .and_then(|e| e.to_str())
                    .unwrap_or("");
                let ext_lower = format!(".{ext}").to_lowercase();
                if let Some(reason) = ext_reason(&ext_lower) {
                    block(&reason);
                    return;
                }
            }
        }
    }

    pass();
}
