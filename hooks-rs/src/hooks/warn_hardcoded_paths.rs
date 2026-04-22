use regex::Regex;

use crate::input::HookInput;
use crate::output::stop;

const TARGET_EXTENSIONS: &[&str] = &[".py", ".go", ".rs"];
const UNIX_PREFIXES: &[&str] = &["/home/", "/usr/", "/etc/", "/var/", "/opt/", "/tmp/"];

fn exclusion_patterns(ext: &str) -> Vec<Regex> {
    match ext {
        "py" => vec![
            Regex::new(r"^\s*#").unwrap(),
            Regex::new(r"^\s*(import|from)\s+").unwrap(),
            Regex::new(r"__file__|Path\s*\(\s*__file__\s*\)").unwrap(),
        ],
        "go" => vec![
            Regex::new(r"^\s*//").unwrap(),
            Regex::new(r"^\s*import\s").unwrap(),
            Regex::new(r"os\.Getenv|filepath\.").unwrap(),
        ],
        "rs" => vec![
            Regex::new(r"^\s*//").unwrap(),
            Regex::new(r"^\s*(use|mod)\s+").unwrap(),
            Regex::new(r"env::var|env!|std::env").unwrap(),
        ],
        _ => vec![],
    }
}

fn scan_content(ext: &str, content: &str) -> Vec<(usize, String)> {
    let exclude = exclusion_patterns(ext);
    let win_drive_re = Regex::new(r"(?:^|[^a-zA-Z0-9])([A-Za-z]:[/\\])").unwrap();
    let escape_re = Regex::new(r"[a-zA-Z]:\\[ntr]").unwrap();

    let mut hits: Vec<(usize, String)> = Vec::new();
    for (i, line) in content.lines().enumerate() {
        if exclude.iter().any(|re| re.is_match(line)) {
            continue;
        }
        let mut found = UNIX_PREFIXES.iter().any(|prefix| line.contains(prefix));
        if !found && let Some(m) = win_drive_re.find(line) {
            let start = m.start();
            if !escape_re.is_match(&line[start..start.saturating_add(4)]) {
                found = true;
            }
        }
        if found {
            hits.push((i + 1, line.to_string()));
        }
    }
    hits
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !TARGET_EXTENSIONS.iter().any(|e| file_path.ends_with(e)) {
        return;
    }

    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");
    let normalized = file_path.replace('\\', "/");
    if normalized.contains("/tests/") || basename == "warn-hardcoded-paths.py" {
        return;
    }

    let ext = std::path::Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");

    let content = match std::fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => return,
    };

    let hits = scan_content(ext, &content);

    if hits.is_empty() {
        return;
    }

    let lines_info: Vec<String> = hits
        .iter()
        .take(5)
        .map(|(num, content)| format!("  L{num}: {content}"))
        .collect();
    let mut detail = lines_info.join("\n");
    if hits.len() > 5 {
        detail.push_str(&format!("\n  ... 他 {} 件", hits.len() - 5));
    }
    stop(&format!(
        "ハードコードされた絶対パスが検出されました。\n{detail}\nパス定数は設定ファイルに集約してください（config/common.toml: no_hardcoded_paths）。"
    ));
}

#[cfg(test)]
mod tests {
    use super::scan_content;

    #[test]
    fn detects_unix_path_in_python() {
        let hits = scan_content("py", "data = \"/home/user/data.csv\"\n");
        assert_eq!(hits.len(), 1);
    }

    #[test]
    fn detects_windows_path_in_python() {
        let hits = scan_content("py", "data = \"C:/Users/foo/bar\"\n");
        assert_eq!(hits.len(), 1);
    }

    #[test]
    fn ignores_comment_line() {
        let hits = scan_content("py", "# config is at /etc/myapp/config.yml\nprint('x')\n");
        assert!(hits.is_empty());
    }

    #[test]
    fn ignores_dynamic_path_from_dunder_file() {
        let hits = scan_content("py", "base = Path(__file__).parent\n");
        assert!(hits.is_empty());
    }

    #[test]
    fn ignores_import_line() {
        let hits = scan_content("py", "from pathlib import Path\n");
        assert!(hits.is_empty());
    }
}
