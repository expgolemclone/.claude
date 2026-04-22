use serde_json::json;

use crate::setup::write_settings;

fn claude_common() -> serde_json::Value {
    json!({
        "model": "claude-opus-4-7",
        "effortLevel": "xhigh",
        "skipDangerousModePermissionPrompt": true,
    })
}

pub fn main() -> i32 {
    let root = match std::env::current_dir() {
        Ok(path) => path,
        Err(err) => {
            eprintln!("{err}");
            return 1;
        }
    };
    let system = match std::env::consts::OS {
        "linux" => "Linux",
        "windows" => "Windows",
        other => {
            eprintln!("Unsupported OS: {other}");
            return 1;
        }
    };
    let binary_path = match std::env::current_exe() {
        Ok(path) => path,
        Err(err) => {
            eprintln!("{err}");
            return 1;
        }
    };
    match write_settings(&root, system, Some(claude_common()), &binary_path) {
        Ok(path) => {
            println!("Generated: {}", path.display());
            0
        }
        Err(err) => {
            eprintln!("{err}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::claude_common;
    use crate::setup::write_settings;
    use tempfile::tempdir;

    #[test]
    fn writes_claude_specific_model_settings() {
        let temp = tempdir().unwrap();
        let root = temp.path().join(".claude");
        std::fs::create_dir_all(&root).unwrap();
        let binary_path = root.join("hooks-rs/target/debug/claude-hooks");

        let target = write_settings(&root, "Linux", Some(claude_common()), &binary_path).unwrap();
        let config: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(target).unwrap()).unwrap();

        assert_eq!(config["model"], "claude-opus-4-7");
        assert_eq!(config["effortLevel"], "xhigh");
        assert_eq!(config["skipDangerousModePermissionPrompt"], true);
    }
}
