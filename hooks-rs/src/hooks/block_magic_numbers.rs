use crate::input::HookInput;
use crate::output;
use crate::python_ast::{LineIndex, call_name, is_numeric_constant, parse_suite, walk_suite};
use rustpython_parser::ast;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

const SAFE_VALUES: &[f64] = &[0.0, 1.0, -1.0];

fn allowlisted_calls() -> HashMap<&'static str, &'static [&'static str]> {
    HashMap::from([
        ("range", &["start", "stop", "step"][..]),
        ("enumerate", &["start"][..]),
        ("round", &["ndigits"][..]),
        ("int", &["base"][..]),
        ("slice", &["start", "stop", "step"][..]),
        ("exit", &["code"][..]),
        ("print", &["end", "sep", "flush"][..]),
        ("open", &["buffering"][..]),
        ("isinstance", &[][..]),
        ("issubclass", &[][..]),
        ("len", &[][..]),
        ("type", &[][..]),
        ("super", &[][..]),
    ])
}

struct Violation {
    line: usize,
    kwarg: String,
    value: String,
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with(".py") || is_test_file(file_path) {
        return;
    }

    let path = Path::new(file_path);
    if !path.is_file() {
        return;
    }

    let Ok(source) = fs::read_to_string(path) else {
        return;
    };
    let Some(suite) = parse_suite(&source, file_path) else {
        return;
    };

    let index = LineIndex::new(&source);
    let allowlisted = allowlisted_calls();
    let mut violations = Vec::new();

    walk_suite(
        &suite,
        &mut |_| {},
        &mut |expr| {
            let ast::Expr::Call(call) = expr else {
                return;
            };
            let func_name = call_name(&call.func).unwrap_or_default();
            let allowed_kwargs = allowlisted.get(func_name).copied();

            for keyword in &call.keywords {
                let Some(arg) = &keyword.arg else {
                    continue;
                };
                let Some((number, value_text)) = is_numeric_constant(&keyword.value) else {
                    continue;
                };
                if SAFE_VALUES.contains(&number) {
                    continue;
                }
                if let Some(allowed) = allowed_kwargs
                    && (allowed.is_empty() || allowed.contains(&arg.as_str()))
                {
                    continue;
                }
                let line = index.line_for(&keyword.value);
                if index.line_text(line).contains("# noqa: magic-number") {
                    continue;
                }
                violations.push(Violation {
                    line,
                    kwarg: arg.to_string(),
                    value: value_text,
                });
            }
        },
        &mut |_| {},
    );

    if violations.is_empty() {
        return;
    }

    let details = violations
        .iter()
        .map(|v| format!("  L{}: {}={}", v.line, v.kwarg, v.value))
        .collect::<Vec<_>>()
        .join("\n");
    let basename = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or(file_path);
    output::stop(&format!(
        "{basename} にマジックナンバーのキーワード引数があります。\n{details}\n設定ファイルまたは名前付き定数を使用してください (# noqa: magic-number で除外可)。"
    ));
}

fn is_test_file(file_path: &str) -> bool {
    let normalized = file_path.replace('\\', "/");
    normalized.contains("/tests/")
        || Path::new(file_path)
            .file_name()
            .and_then(|s| s.to_str())
            .is_some_and(|name| name.starts_with("test_"))
}
