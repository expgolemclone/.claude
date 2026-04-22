use crate::git::run_git;
use crate::input::HookInput;
use crate::output::{block, pass};

fn build_issues(uncommitted: &str, upstream: &str, unpushed: &str) -> String {
    let mut issues = String::new();

    if !uncommitted.is_empty() {
        issues.push_str(&format!("Uncommitted changes detected:\n{uncommitted}\n\n"));
    }

    if !upstream.is_empty() && !unpushed.is_empty() {
        issues.push_str(&format!("Unpushed commits detected:\n{unpushed}\n\n"));
    }

    issues
}

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }
    let cwd = &input.cwd;
    if cwd.is_empty() {
        return;
    }
    let cwd_path = std::path::Path::new(cwd);

    if run_git(cwd_path, &["rev-parse", "--is-inside-work-tree"]).is_empty() {
        return;
    }

    let uncommitted = run_git(cwd_path, &["status", "--porcelain"]);
    let upstream = run_git(cwd_path, &["rev-parse", "--abbrev-ref", "@{upstream}"]);
    let unpushed = if upstream.is_empty() {
        String::new()
    } else {
        run_git(cwd_path, &["log", "@{upstream}..HEAD", "--oneline"])
    };
    let issues = build_issues(&uncommitted, &upstream, &unpushed);

    if !issues.is_empty() {
        block(&format!(
            "{issues}Run the code and verify it works, then commit and push all changes."
        ));
        return;
    }
    pass();
}

#[cfg(test)]
mod tests {
    use super::build_issues;

    #[test]
    fn reports_uncommitted_changes() {
        assert!(build_issues(" M file.txt", "", "").contains("Uncommitted changes detected"));
    }

    #[test]
    fn reports_unpushed_commits_when_upstream_exists() {
        assert!(
            build_issues("", "origin/main", "abc123 msg").contains("Unpushed commits detected")
        );
    }

    #[test]
    fn ignores_unpushed_commits_without_upstream() {
        assert!(build_issues("", "", "abc123 msg").is_empty());
    }

    #[test]
    fn combines_both_issue_types() {
        let issues = build_issues(" M file.txt", "origin/main", "abc123 msg");
        assert!(issues.contains("Uncommitted changes detected"));
        assert!(issues.contains("Unpushed commits detected"));
    }
}
