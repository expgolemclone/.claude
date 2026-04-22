use regex::Regex;

use crate::git::git_tracked_files;
use crate::input::HookInput;
use crate::output::block;

const NOQA_MARKER: &str = "# noqa: fullwidth-punctuation";

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }
    let cwd = &input.cwd;
    if cwd.is_empty() {
        return;
    }

    let re = Regex::new(
        r"[。，；：！？「」『』【】〈〉《》〔〕（）……——·〜～\x{201c}\x{201d}\x{2018}\x{2019}]",
    )
    .unwrap();
    let root = std::path::Path::new(cwd);
    let mut all_violations: Vec<String> = Vec::new();

    for file_path in git_tracked_files(root, &[]) {
        if !file_path.is_file() {
            continue;
        }
        let text = match std::fs::read_to_string(&file_path) {
            Ok(t) => t,
            Err(_) => continue,
        };
        for (i, line) in text.lines().enumerate() {
            if line.contains(NOQA_MARKER) {
                continue;
            }
            if re.is_match(line) {
                let found: Vec<&str> = re.find_iter(line).map(|m| m.as_str()).collect();
                all_violations.push(format!("{}:{} {:?}", file_path.display(), i + 1, found));
            }
        }
    }

    if !all_violations.is_empty() {
        let detail = all_violations
            .iter()
            .take(50)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n");
        let extra = if all_violations.len() > 50 {
            format!("\n  ... 他 {} 件", all_violations.len() - 50)
        } else {
            String::new()
        };
        block(&format!(
            "全角句読点が {} 箇所で見つかりました:\n{detail}{extra}\n\n半角記号を使用してください。除外する場合は行末に {NOQA_MARKER} を追加してください。",
            all_violations.len()
        ));
    }
}
