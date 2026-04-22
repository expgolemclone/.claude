use regex::Regex;

use crate::git::strip_quotes;
use crate::input::HookInput;
use crate::output::{block, pass};

pub fn run(input: &HookInput) {
    let command = &input.tool_input.command;
    if command.is_empty() {
        return;
    }
    let stripped = strip_quotes(command);
    let boundary = r"(?:^|(?:&&|\|\||[;|`]|\$\()\s*)";
    let sudo = r"(?:sudo\s+)?";

    let uv_sync_re = Regex::new(&format!("{boundary}uv\\s+(?:pip\\s+)?sync\\b")).unwrap();
    let npm_ci_re = Regex::new(&format!("{boundary}{sudo}npm\\s+ci\\b")).unwrap();
    if uv_sync_re.is_match(&stripped) || npm_ci_re.is_match(&stripped) {
        return;
    }

    let pip_install_re =
        Regex::new(&format!("{boundary}{sudo}(?:uv\\s+)?pip3?\\s+install\\b")).unwrap();
    let pip_req_re = Regex::new(r"\s+(?:-r|--requirement)\b").unwrap();
    if pip_install_re.is_match(&stripped) && !pip_req_re.is_match(&stripped) {
        block(
            "lockfileを経由しないパッケージインストールは禁止です（config: install_without_lock = false）。\nuv pip install -r requirements.txt または uv sync を使用してください。",
        );
        return;
    }

    let yarn_re = Regex::new(&format!("{boundary}{sudo}yarn\\s+add\\b")).unwrap();
    if yarn_re.is_match(&stripped) {
        block(
            "lockfileを経由しないパッケージインストールは禁止です（config: install_without_lock = false）。\nnpm ci または yarn install --frozen-lockfile を使用してください。",
        );
        return;
    }

    let npm_install_re = Regex::new(&format!("{boundary}{sudo}npm\\s+install\\b")).unwrap();
    let npm_no_lock_re = Regex::new(r"--no-package-lock").unwrap();
    if npm_install_re.is_match(&stripped) && npm_no_lock_re.is_match(&stripped) {
        block(
            "--no-package-lock 付きのインストールは禁止です（config: install_without_lock = false）。\nnpm ci を使用してください。",
        );
        return;
    }

    let cargo_install_re = Regex::new(&format!("{boundary}{sudo}cargo\\s+install\\b")).unwrap();
    if cargo_install_re.is_match(&stripped) {
        block(
            "cargo install は lockfile を経由しません（config: install_without_lock = false）。\nCargo.toml に依存を追加し cargo build を使用してください。",
        );
        return;
    }

    pass();
}
