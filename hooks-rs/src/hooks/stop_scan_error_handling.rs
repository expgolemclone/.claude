use crate::git::git_tracked_py_files;
use crate::input::HookInput;
use crate::output::block;
use crate::python_ast::{LineIndex, call_name, parse_suite, walk_stmt, walk_suite};
use rustpython_parser::ast;
use std::fs;
use std::path::{Path, PathBuf};

const BROAD_EXCEPT_NAMES: &[&str] = &["Exception", "BaseException"];
const NOTIFICATION_ATTRS: &[&str] = &[
    "error",
    "warning",
    "warn",
    "info",
    "debug",
    "critical",
    "exception",
    "fatal",
    "log",
];
const NOTIFICATION_NAMES: &[&str] = &["print", "log"];

struct Violation {
    line: usize,
    col: usize,
    rule: &'static str,
    snippet: String,
}

pub fn run(input: &HookInput) {
    if input.stop_hook_active || input.permission_mode == "plan" || input.cwd.is_empty() {
        return;
    }

    let root = Path::new(&input.cwd);
    let hooks_dir = home::home_dir()
        .unwrap_or_default()
        .join(".claude")
        .join("hooks");
    let mut all_violations = Vec::new();

    for py_file in git_tracked_py_files(root) {
        if is_under_hooks_dir(&py_file, &hooks_dir) {
            continue;
        }
        let Ok(source) = fs::read_to_string(&py_file) else {
            continue;
        };
        for violation in check_python(&source, &py_file) {
            all_violations.push(format!(
                "  {}:L{}:{} [{}] {}",
                py_file.display(),
                violation.line,
                violation.col,
                violation.rule,
                violation.snippet
            ));
        }
    }

    if all_violations.is_empty() {
        return;
    }

    let detail = all_violations.join("\n");
    block(&format!(
        "error_handling 違反が {} 件見つかりました:\n{detail}\n\nno_bare_except: 具体的な例外型を指定してください。\nno_silent_swallow: ログ出力か再送出してください。",
        all_violations.len()
    ));
}

fn check_python(source: &str, path: &Path) -> Vec<Violation> {
    let Some(suite) = parse_suite(source, &path.display().to_string()) else {
        return Vec::new();
    };
    let index = LineIndex::new(source);
    let mut violations = Vec::new();

    walk_suite(&suite, &mut |_| {}, &mut |_| {}, &mut |handler| {
        if is_broad_except(handler.type_.as_deref()) {
            push_violation(&mut violations, &index, handler, "no_bare_except");
        }
        if is_silent_body(&handler.body) {
            push_violation(&mut violations, &index, handler, "no_silent_swallow");
        }
    });
    violations
}

fn is_broad_except(exc_type: Option<&ast::Expr>) -> bool {
    match exc_type {
        None => true,
        Some(ast::Expr::Name(name)) => BROAD_EXCEPT_NAMES.contains(&name.id.as_str()),
        Some(ast::Expr::Tuple(tuple)) => tuple.elts.iter().any(|expr| {
            matches!(expr, ast::Expr::Name(name) if BROAD_EXCEPT_NAMES.contains(&name.id.as_str()))
        }),
        _ => false,
    }
}

fn is_silent_body(body: &[ast::Stmt]) -> bool {
    if body.is_empty() || has_raise(body) || has_notification_call(body) || body.len() != 1 {
        return false;
    }
    match &body[0] {
        ast::Stmt::Pass(_) => true,
        ast::Stmt::Return(node) => node.value.as_deref().is_none_or(is_trivial_value),
        ast::Stmt::Assign(node) => is_trivial_value(&node.value),
        _ => false,
    }
}

fn has_raise(stmts: &[ast::Stmt]) -> bool {
    let mut found = false;
    for stmt in stmts {
        walk_stmt(
            stmt,
            &mut |stmt| {
                if matches!(stmt, ast::Stmt::Raise(_)) {
                    found = true;
                }
            },
            &mut |_| {},
            &mut |_| {},
        );
    }
    found
}

fn has_notification_call(stmts: &[ast::Stmt]) -> bool {
    let mut found = false;
    for stmt in stmts {
        walk_stmt(
            stmt,
            &mut |_| {},
            &mut |expr| {
                let ast::Expr::Call(call) = expr else {
                    return;
                };
                if let Some(name) = call_name(&call.func)
                    && NOTIFICATION_NAMES.contains(&name)
                {
                    found = true;
                }
                if let ast::Expr::Attribute(attr) = call.func.as_ref()
                    && NOTIFICATION_ATTRS.contains(&attr.attr.as_str())
                {
                    found = true;
                }
            },
            &mut |_| {},
        );
    }
    found
}

fn is_trivial_value(expr: &ast::Expr) -> bool {
    match expr {
        ast::Expr::Constant(_) => true,
        ast::Expr::List(node) => node.elts.is_empty(),
        ast::Expr::Tuple(node) => node.elts.is_empty(),
        ast::Expr::Set(node) => node.elts.is_empty(),
        ast::Expr::Dict(node) => node.keys.is_empty(),
        _ => false,
    }
}

fn push_violation<T: rustpython_parser::ast::Ranged>(
    violations: &mut Vec<Violation>,
    index: &LineIndex,
    node: &T,
    rule: &'static str,
) {
    let (line, col) = index.line_col_for(node);
    violations.push(Violation {
        line,
        col,
        rule,
        snippet: index.snippet_for(node),
    });
}

fn is_under_hooks_dir(path: &Path, hooks_dir: &Path) -> bool {
    let path = normalize_path(path);
    let hooks_dir = normalize_path(hooks_dir);
    path.starts_with(hooks_dir)
}

fn normalize_path(path: &Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| path.to_path_buf())
}
