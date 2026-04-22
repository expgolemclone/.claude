use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize, Default)]
#[allow(dead_code)]
pub struct HookInput {
    #[serde(default)]
    pub tool_name: String,
    #[serde(default)]
    pub tool_input: ToolInput,
    #[serde(default)]
    pub stop_hook_active: bool,
    #[serde(default)]
    pub permission_mode: String,
    #[serde(default)]
    pub cwd: String,
    #[serde(default)]
    pub transcript_path: String,
}

#[derive(Deserialize, Default)]
pub struct ToolInput {
    #[serde(default)]
    pub file_path: String,
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub command: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub new_string: String,
    #[serde(default)]
    pub old_string: String,
}

impl ToolInput {
    pub fn file_path_resolved(&self) -> &str {
        if self.file_path.is_empty() {
            &self.path
        } else {
            &self.file_path
        }
    }
}

pub fn read_input() -> Result<HookInput, String> {
    let mut buf = String::new();
    io::stdin()
        .read_to_string(&mut buf)
        .map_err(|e| e.to_string())?;
    serde_json::from_str(&buf).map_err(|e| e.to_string())
}
