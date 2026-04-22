use std::path::PathBuf;
use std::process::Command;

pub fn git_tracked_files(root: &std::path::Path, patterns: &[&str]) -> Vec<PathBuf> {
    let mut cmd = Command::new("git");
    cmd.arg("ls-files");
    if !patterns.is_empty() {
        cmd.arg("--");
        cmd.args(patterns);
    }
    let output = match cmd.current_dir(root).output() {
        Ok(o) => o,
        Err(_) => return Vec::new(),
    };
    if !output.status.success() {
        return Vec::new();
    }
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter(|l| !l.is_empty())
        .map(|l| root.join(l))
        .collect()
}

pub fn git_tracked_py_files(root: &std::path::Path) -> Vec<PathBuf> {
    git_tracked_files(root, &["*.py"])
}

pub fn run_git(cwd: &std::path::Path, args: &[&str]) -> String {
    let output = Command::new("git").current_dir(cwd).args(args).output();
    match output {
        Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).trim().to_string(),
        _ => String::new(),
    }
}

pub fn strip_quotes(command: &str) -> String {
    let re1 = regex::Regex::new(r#""[^"]*""#).unwrap();
    let re2 = regex::Regex::new(r"'[^']*'").unwrap();
    let s = re1.replace_all(command, r#""""#);
    re2.replace_all(&s, "''").to_string()
}
