use crate::git::run_git;
use crate::input::HookInput;
use crate::output::{block, pass};

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

    let mut issues = String::new();

    let uncommitted = run_git(cwd_path, &["status", "--porcelain"]);
    if !uncommitted.is_empty() {
        issues.push_str(&format!("Uncommitted changes detected:\n{uncommitted}\n\n"));
    }

    let upstream = run_git(cwd_path, &["rev-parse", "--abbrev-ref", "@{upstream}"]);
    if !upstream.is_empty() {
        let unpushed = run_git(cwd_path, &["log", "@{upstream}..HEAD", "--oneline"]);
        if !unpushed.is_empty() {
            issues.push_str(&format!("Unpushed commits detected:\n{unpushed}\n\n"));
        }
    }

    if !issues.is_empty() {
        block(&format!(
            "{issues}Run the code and verify it works, then commit and push all changes."
        ));
        return;
    }
    pass();
}
