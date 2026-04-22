use std::path::PathBuf;

use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    let settings_path = home_dir().join(".claude").join("settings.json");

    let canonical_file = std::fs::canonicalize(file_path);
    let canonical_settings = std::fs::canonicalize(&settings_path);

    if let (Ok(cf), Ok(cs)) = (canonical_file, canonical_settings)
        && cf == cs
    {
        block("settings.json は setup.py から生成されます。`uv run python setup.py`");
        return;
    }

    // ファイルが存在しない場合でもパス文字列の比較で判定
    if file_path.ends_with(".claude/settings.json") {
        block("settings.json は setup.py から生成されます。`uv run python setup.py`");
        return;
    }

    pass();
}

fn home_dir() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/root"))
}
