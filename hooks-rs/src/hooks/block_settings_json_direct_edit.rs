use std::path::PathBuf;

use crate::input::HookInput;
use crate::output::{block, pass};

fn is_settings_json_edit(file_path: &str, settings_path: &std::path::Path) -> bool {
    let canonical_file = std::fs::canonicalize(file_path);
    let canonical_settings = std::fs::canonicalize(settings_path);

    if let (Ok(cf), Ok(cs)) = (canonical_file, canonical_settings)
        && cf == cs
    {
        return true;
    }

    file_path.ends_with(".claude/settings.json")
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() {
        return;
    }

    let settings_path = home_dir().join(".claude").join("settings.json");
    if is_settings_json_edit(file_path, &settings_path) {
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

#[cfg(test)]
mod tests {
    use super::is_settings_json_edit;
    use tempfile::tempdir;

    #[test]
    fn blocks_exact_settings_path() {
        let dir = tempdir().unwrap();
        let claude_dir = dir.path().join(".claude");
        std::fs::create_dir_all(&claude_dir).unwrap();
        let settings = claude_dir.join("settings.json");
        std::fs::write(&settings, "{}").unwrap();

        assert!(is_settings_json_edit(
            &settings.display().to_string(),
            &settings
        ));
    }

    #[test]
    fn blocks_suffix_match_even_without_existing_file() {
        let dir = tempdir().unwrap();
        let settings = dir.path().join(".claude").join("settings.json");

        assert!(is_settings_json_edit(
            "/tmp/user/.claude/settings.json",
            &settings
        ));
    }

    #[test]
    fn allows_other_json_file() {
        let dir = tempdir().unwrap();
        let settings = dir.path().join(".claude").join("settings.json");

        assert!(!is_settings_json_edit(
            "/tmp/user/.claude/other.json",
            &settings
        ));
    }

    #[test]
    fn allows_settings_json_in_other_directory() {
        let dir = tempdir().unwrap();
        let settings = dir.path().join(".claude").join("settings.json");

        assert!(!is_settings_json_edit(
            "/tmp/project/settings.json",
            &settings
        ));
    }
}
