use std::io::{self, BufRead, BufReader};
use std::path::Path;

#[derive(Default)]
pub struct ToolUseEntry {
    pub tool_name: String,
    pub file_path: String,
}

pub fn read_transcript(path: &Path) -> Vec<serde_json::Value> {
    read_transcript_checked(path).unwrap_or_default()
}

pub fn read_transcript_checked(path: &Path) -> io::Result<Vec<serde_json::Value>> {
    let file = std::fs::File::open(path)?;
    let reader = BufReader::new(file);
    let mut entries = Vec::new();
    for line in reader.lines().map_while(Result::ok) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line) {
            entries.push(val);
        }
    }
    Ok(entries)
}

pub fn extract_tool_uses(entries: &[serde_json::Value]) -> Vec<ToolUseEntry> {
    let mut results = Vec::new();
    for entry in entries {
        let content = match entry.get("message").and_then(|m| m.get("content")) {
            Some(c) => c,
            None => continue,
        };
        let blocks = match content.as_array() {
            Some(a) => a,
            None => continue,
        };
        for block in blocks {
            if block.get("type").and_then(|t| t.as_str()) != Some("tool_use") {
                continue;
            }
            let name = block
                .get("name")
                .and_then(|n| n.as_str())
                .unwrap_or("")
                .to_string();
            let input = block.get("input").cloned().unwrap_or_default();
            let file_path = input
                .get("file_path")
                .or_else(|| input.get("path"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            results.push(ToolUseEntry {
                tool_name: name,
                file_path,
            });
        }
    }
    results
}

pub fn find_last_real_user_idx(entries: &[serde_json::Value]) -> Option<usize> {
    for i in (0..entries.len()).rev() {
        let entry = &entries[i];
        if entry.get("type").and_then(|t| t.as_str()) != Some("user") {
            continue;
        }
        let content = match entry
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_array())
        {
            Some(a) => a,
            None => continue,
        };
        let all_tool_results = content
            .iter()
            .all(|b| b.get("type").and_then(|t| t.as_str()) == Some("tool_result"));
        if !all_tool_results {
            return Some(i);
        }
    }
    None
}
