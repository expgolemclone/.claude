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

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }

    let transcript_path = &input.transcript_path;
    if transcript_path.is_empty() {
        return;
    }

    let entries = transcript::read_transcript(Path::new(transcript_path));
    let last_user_idx = match transcript::find_last_real_user_idx(&entries) {
        Some(i) => i,
        None => return,
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

    if used_search || used_coding_tool {
        return;
    }

    block(
        "This response lacks primary source verification.\n\
         If answering a knowledge-based question, verify with WebSearch or \
         WebFetch before responding.\n\
         If responding to a coding task, you may proceed without verification.",
    );
}
