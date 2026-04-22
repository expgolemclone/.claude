use std::path::Path;

use crate::input::HookInput;
use crate::output::block;
use crate::transcript;

const ARCHITECTURE_FILENAME: &str = "ARCHITECTURE.md";
const EDIT_TOOLS: &[&str] = &["Edit", "Write"];

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }

    let transcript_path = &input.transcript_path;
    if transcript_path.is_empty() {
        return;
    }

    let entries = transcript::read_transcript(Path::new(transcript_path));
    let tool_uses = transcript::extract_tool_uses(&entries);

    let mut edited_non_arch = false;
    let mut edited_arch = false;

    for tu in &tool_uses {
        if !EDIT_TOOLS.contains(&tu.tool_name.as_str()) {
            continue;
        }
        if Path::new(&tu.file_path)
            .file_name()
            .and_then(|n| n.to_str())
            == Some(ARCHITECTURE_FILENAME)
        {
            edited_arch = true;
        } else {
            edited_non_arch = true;
        }
    }

    if !edited_non_arch {
        return;
    }

    let cwd = &input.cwd;
    let arch_exists = if !cwd.is_empty() {
        Path::new(cwd).join(ARCHITECTURE_FILENAME).is_file()
    } else {
        false
    };

    if !arch_exists {
        block(
            "ARCHITECTURE.md が存在しません。\nファイル構成の変更を反映するため作成してください。",
        );
        return;
    }

    if !edited_arch {
        block(
            "ファイルを編集しましたが ARCHITECTURE.md を更新していません。\n変更内容を反映してください。",
        );
    }
}
