use std::path::Path;

use crate::input::HookInput;
use crate::output::block;
use crate::transcript;

const SEARCH_TOOLS: &[&str] = &["WebSearch", "WebFetch"];
const CODING_TOOLS: &[&str] = &[
    "Edit",
    "Write",
    "Bash",
    "Read",
    "Grep",
    "Glob",
    "NotebookEdit",
];

fn should_block_entries(entries: &[serde_json::Value]) -> bool {
    let last_user_idx = match transcript::find_last_real_user_idx(entries) {
        Some(i) => i,
        None => return false,
    };

    let mut used_search = false;
    let mut used_coding_tool = false;

    for entry in entries.iter().skip(last_user_idx + 1) {
        let content = match entry
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_array())
        {
            Some(a) => a,
            None => continue,
        };
        for blk in content {
            if blk.get("type").and_then(|t| t.as_str()) != Some("tool_use") {
                continue;
            }
            if let Some(name) = blk.get("name").and_then(|n| n.as_str()) {
                if SEARCH_TOOLS.contains(&name) {
                    used_search = true;
                }
                if CODING_TOOLS.contains(&name) {
                    used_coding_tool = true;
                }
            }
        }
        if used_search {
            break;
        }
    }

    !(used_search || used_coding_tool)
}

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }

    let transcript_path = &input.transcript_path;
    if transcript_path.is_empty() {
        return;
    }

    let entries = transcript::read_transcript(Path::new(transcript_path));
    if !should_block_entries(&entries) {
        return;
    }

    block(
        "This response lacks primary source verification.\n\
         If answering a knowledge-based question, verify with WebSearch or \
         WebFetch before responding.\n\
         If responding to a coding task, you may proceed without verification.",
    );
}

#[cfg(test)]
mod tests {
    use super::should_block_entries;
    use serde_json::json;

    #[test]
    fn web_search_allows_response() {
        let entries = vec![
            json!({"type":"user","message":{"content":[{"type":"text","text":"Hello"}]}}),
            json!({"type":"assistant","message":{"content":[{"type":"tool_use","name":"WebSearch"}]}}),
        ];

        assert!(!should_block_entries(&entries));
    }

    #[test]
    fn coding_tool_allows_response() {
        let entries = vec![
            json!({"type":"user","message":{"content":[{"type":"text","text":"Hello"}]}}),
            json!({"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read"}]}}),
        ];

        assert!(!should_block_entries(&entries));
    }

    #[test]
    fn unrelated_tool_still_blocks() {
        let entries = vec![
            json!({"type":"user","message":{"content":[{"type":"text","text":"Hello"}]}}),
            json!({"type":"assistant","message":{"content":[{"type":"tool_use","name":"SomeOtherTool"}]}}),
        ];

        assert!(should_block_entries(&entries));
    }

    #[test]
    fn no_tool_use_blocks() {
        let entries = vec![
            json!({"type":"user","message":{"content":[{"type":"text","text":"Hello"}]}}),
            json!({"type":"assistant","message":{"content":[{"type":"text","text":"response"}]}}),
        ];

        assert!(should_block_entries(&entries));
    }
}
