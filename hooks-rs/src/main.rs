mod git;
mod hooks;
mod input;
mod nix_protected;
mod output;
mod patch_clawd_mascot;
mod process;
mod project_root;
mod python_ast;
mod setup;
mod setup_claude;
mod transcript;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let subcommand = args.get(1).map(String::as_str).unwrap_or_default();

    match subcommand {
        "patch-clawd-mascot" => std::process::exit(patch_clawd_mascot::main(&args[2..])),
        "setup" => std::process::exit(setup::main()),
        "setup-claude" => std::process::exit(setup_claude::main()),
        _ => {}
    }

    let input = match input::read_input() {
        Ok(v) => v,
        Err(_) => return,
    };

    match subcommand {
        "block-any-type" => hooks::block_any_type::run(&input),
        "block-commit-without-verification" => {
            hooks::block_commit_without_verification::run(&input)
        }
        "block-git-add-force-staging" => hooks::block_git_add_force_staging::run(&input),
        "block-git-commit-prohibited-keywords" => {
            hooks::block_git_commit_prohibited_keywords::run(&input)
        }
        "block-git-commit-protected-changes" => {
            hooks::block_git_commit_protected_changes::run(&input)
        }
        "block-install-without-lock" => hooks::block_install_without_lock::run(&input),
        "block-magic-numbers" => hooks::block_magic_numbers::run(&input),
        "block-manual-requirements-txt" => hooks::block_manual_requirements_txt::run(&input),
        "block-missing-annotations" => hooks::block_missing_annotations::run(&input),
        "block-nixos-rebuild-protected-changes" => {
            hooks::block_nixos_rebuild_protected_changes::run(&input)
        }
        "block-non-python-hook-scripts" => hooks::block_non_python_hook_scripts::run(&input),
        "block-platform-specific-scripts" => hooks::block_platform_specific_scripts::run(&input),
        "block-prohibited-python-toolchains" => {
            hooks::block_prohibited_python_toolchains::run(&input)
        }
        "block-protected-nix-config" => hooks::block_protected_nix_config::run(&input),
        "block-scrape-interval" => hooks::block_scrape_interval::run(&input),
        "block-settings-json-direct-edit" => hooks::block_settings_json_direct_edit::run(&input),
        "block-setup-py-cfg" => hooks::block_setup_py_cfg::run(&input),
        "block-unbounded-dependency" => hooks::block_unbounded_dependency::run(&input),
        "block-wildcard-versions" => hooks::block_wildcard_versions::run(&input),
        "block-worker-in-tracked-datasource" => {
            hooks::block_worker_in_tracked_datasource::run(&input)
        }
        "check-hotstring-conflicts" => hooks::check_hotstring_conflicts::run(&input),
        "inject-extension-rules-toml" => hooks::inject_extension_rules_toml::run(&input),
        "post-auto-setup" => hooks::post_auto_setup::run(&input),
        "post-cargo-clippy-on-rs-edit" => hooks::post_cargo_clippy_on_rs_edit::run(&input),
        "post-oxisym-scan" => hooks::post_oxisym_scan::run(&input),
        "post-scan-fallbacks" => hooks::post_scan_fallbacks::run(&input),
        "post-verify-protected-nix-config" => hooks::post_verify_protected_nix_config::run(&input),
        "stop-lint-edited-python" => hooks::stop_lint_edited_python::run(&input),
        "stop-nixos-rebuild-on-config-change" => {
            hooks::stop_nixos_rebuild_on_config_change::run(&input)
        }
        "stop-prompt-architecture-md" => hooks::stop_prompt_architecture_md::run(&input),
        "stop-require-git-commit-and-push" => hooks::stop_require_git_commit_and_push::run(&input),
        "stop-require-source-verification" => hooks::stop_require_source_verification::run(&input),
        "stop-scan-any-type" => hooks::stop_scan_any_type::run(&input),
        "stop-scan-error-handling" => hooks::stop_scan_error_handling::run(&input),
        "stop-scan-fullwidth-punctuation" => hooks::stop_scan_fullwidth_punctuation::run(&input),
        "stop-update-and-patch-claude" => hooks::stop_update_and_patch_claude::run(&input),
        "stop-warn-chrome-tabs" => hooks::stop_warn_chrome_tabs::run(&input),
        "warn-gitignore-not-whitelist" => hooks::warn_gitignore_not_whitelist::run(&input),
        "warn-hardcoded-paths" => hooks::warn_hardcoded_paths::run(&input),
        "warn-structural-duplicates" => hooks::warn_structural_duplicates::run(&input),
        _ => {}
    }
}
