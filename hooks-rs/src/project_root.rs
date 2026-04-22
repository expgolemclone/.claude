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

#[cfg(test)]
mod tests {
    use super::{find_git_root, find_project_root};
    use tempfile::tempdir;

    #[test]
    fn finds_project_root_in_same_dir() {
        let dir = tempdir().unwrap();
        std::fs::write(dir.path().join("Cargo.toml"), "").unwrap();

        assert_eq!(
            find_project_root(dir.path(), "Cargo.toml"),
            Some(dir.path().to_path_buf())
        );
    }

    #[test]
    fn finds_project_root_in_parent_dir() {
        let dir = tempdir().unwrap();
        std::fs::write(dir.path().join("Cargo.toml"), "").unwrap();
        let sub = dir.path().join("src");
        std::fs::create_dir(&sub).unwrap();

        assert_eq!(
            find_project_root(&sub, "Cargo.toml"),
            Some(dir.path().to_path_buf())
        );
    }

    #[test]
    fn returns_none_without_project_marker() {
        let dir = tempdir().unwrap();
        let sub = dir.path().join("isolated");
        std::fs::create_dir(&sub).unwrap();

        assert_eq!(find_project_root(&sub, "Cargo.toml"), None);
    }

    #[test]
    fn finds_git_root_with_git_dir() {
        let dir = tempdir().unwrap();
        std::fs::create_dir(dir.path().join(".git")).unwrap();

        assert_eq!(find_git_root(dir.path()), Some(dir.path().to_path_buf()));
    }

    #[test]
    fn finds_git_root_with_git_file_in_parent() {
        let dir = tempdir().unwrap();
        std::fs::write(dir.path().join(".git"), "gitdir: /tmp/other\n").unwrap();
        let sub = dir.path().join("src");
        std::fs::create_dir(&sub).unwrap();

        assert_eq!(find_git_root(&sub), Some(dir.path().to_path_buf()));
    }
}
