use std::path::Path;

pub fn find_project_root(start: &Path, marker: &str) -> Option<std::path::PathBuf> {
    let mut d = if start.is_absolute() {
        start.to_path_buf()
    } else {
        std::fs::canonicalize(start).ok()?
    };
    loop {
        if d.join(marker).is_file() {
            return Some(d);
        }
        match d.parent() {
            Some(p) if p != d => d = p.to_path_buf(),
            _ => return None,
        }
    }
}

pub fn find_git_root(start: &Path) -> Option<std::path::PathBuf> {
    let mut d = if start.is_absolute() {
        start.to_path_buf()
    } else {
        std::fs::canonicalize(start).ok()?
    };
    loop {
        let git = d.join(".git");
        if git.is_dir() || git.is_file() {
            return Some(d);
        }
        match d.parent() {
            Some(p) if p != d => d = p.to_path_buf(),
            _ => return None,
        }
    }
}
