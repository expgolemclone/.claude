use crate::input::HookInput;
use crate::python_ast::{LineIndex, call_name, is_none_constant, parse_suite, walk_suite};
use rustpython_parser::ast;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use toml::Value;

const DEFAULT_FN_NAMES: &[&str] = &["_prefer", "fallback", "coalesce", "_default"];
const DEFAULT_FN_PREFIXES: &[&str] = &["safe_", "_safe_"];

struct Finding {
    file: String,
    line: usize,
    col: usize,
    pattern: &'static str,
    snippet: String,
}

impl std::fmt::Display for Finding {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}:{}:{} [{}] {}",
            self.file, self.line, self.col, self.pattern, self.snippet
        )
    }
}

struct Config {
    scan_roots: HashSet<String>,
    exclude_dirs: HashSet<String>,
    fn_names: HashSet<String>,
    fn_prefixes: Vec<String>,
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with(".py") {
        return;
    }

    let Ok(project_root_raw) = std::env::current_dir() else {
        return;
    };
    let project_root = project_root_raw.canonicalize().unwrap_or(project_root_raw);
    let Some(config) = load_config(&project_root) else {
        return;
    };

    let path = normalize_path(&absolute_path(file_path, &project_root));
    if !path.is_file() {
        return;
    }
    let Ok(rel_path) = path.strip_prefix(&project_root) else {
        return;
    };
    let parts = rel_path
        .components()
        .filter_map(|c| c.as_os_str().to_str())
        .collect::<Vec<_>>();
    if parts.is_empty() || !config.scan_roots.contains(parts[0]) {
        return;
    }
    if parts.iter().any(|part| config.exclude_dirs.contains(*part)) {
        return;
    }

    let rel_display = rel_path.display().to_string();
    let findings = scan_file(&path, &rel_display, &config);
    if findings.is_empty() {
        return;
    }

    let details = findings
        .iter()
        .map(|f| format!("  {f}"))
        .collect::<Vec<_>>()
        .join("\n");
    eprintln!(
        "[info] fallback パターンが検出されました:\n{details}\nfail_fast ルールに基づき文脈判断してください。正当な用途（optional dependency, 設定のデフォルト値等）は問題ありません。"
    );
}

fn load_config(project_root: &Path) -> Option<Config> {
    let path = project_root.join("config").join("scan_fallbacks.toml");
    if !path.is_file() {
        return None;
    }
    let source = fs::read_to_string(path).ok()?;
    let data: Value = toml::from_str(&source).ok()?;
    let section = data.get("scan_fallbacks").and_then(Value::as_table);
    let scan_roots = read_string_set(section.and_then(|s| s.get("scan_roots")));
    let exclude_dirs = read_string_set(section.and_then(|s| s.get("exclude_dirs")));

    let functions = section
        .and_then(|s| s.get("functions"))
        .and_then(Value::as_table);
    let fn_names = read_string_set(functions.and_then(|s| s.get("names")))
        .into_iter()
        .chain(DEFAULT_FN_NAMES.iter().map(|s| (*s).to_string()))
        .collect();
    let configured_prefixes = read_string_vec(functions.and_then(|s| s.get("prefixes")));
    let fn_prefixes = if configured_prefixes.is_empty() {
        DEFAULT_FN_PREFIXES
            .iter()
            .map(|s| (*s).to_string())
            .collect()
    } else {
        configured_prefixes
    };

    Some(Config {
        scan_roots,
        exclude_dirs,
        fn_names,
        fn_prefixes,
    })
}

fn read_string_set(value: Option<&Value>) -> HashSet<String> {
    read_string_vec(value).into_iter().collect()
}

fn read_string_vec(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn scan_file(path: &Path, rel_display: &str, config: &Config) -> Vec<Finding> {
    let Ok(source) = fs::read_to_string(path) else {
        return Vec::new();
    };
    let Some(suite) = parse_suite(&source, &path.display().to_string()) else {
        return Vec::new();
    };
    let index = LineIndex::new(&source);
    let mut stmt_findings = Vec::new();
    let mut expr_findings = Vec::new();

    walk_suite(
        &suite,
        &mut |stmt| scan_stmt(stmt, rel_display, &index, &mut stmt_findings),
        &mut |expr| scan_expr(expr, rel_display, &index, config, &mut expr_findings),
        &mut |_| {},
    );
    let mut findings = stmt_findings;
    findings.extend(expr_findings);
    findings.extend(scan_fallback_comments(&source, rel_display));
    findings
}

fn scan_stmt(stmt: &ast::Stmt, rel_display: &str, index: &LineIndex, findings: &mut Vec<Finding>) {
    match stmt {
        ast::Stmt::Try(node) => scan_try(&node.body, &node.handlers, rel_display, index, findings),
        ast::Stmt::TryStar(node) => {
            scan_try(&node.body, &node.handlers, rel_display, index, findings)
        }
        ast::Stmt::If(node) => {
            if is_none_check(&node.test)
                && node.body.len() == 1
                && matches!(node.body[0], ast::Stmt::Assign(_) | ast::Stmt::AugAssign(_))
            {
                push_finding(findings, rel_display, index, stmt, "if_none_assign");
            }
        }
        _ => {}
    }
}

fn scan_try(
    body: &[ast::Stmt],
    handlers: &[ast::ExceptHandler],
    rel_display: &str,
    index: &LineIndex,
    findings: &mut Vec<Finding>,
) {
    let body_is_imports = !body.is_empty()
        && body
            .iter()
            .all(|s| matches!(s, ast::Stmt::Import(_) | ast::Stmt::ImportFrom(_)));
    for handler in handlers {
        let ast::ExceptHandler::ExceptHandler(handler) = handler;
        if body_is_imports && handler_is_importerror(handler) {
            push_finding(findings, rel_display, index, handler, "import_fallback");
        }
        if handler_is_swallow(handler) {
            push_finding(findings, rel_display, index, handler, "try_except_swallow");
        }
    }
}

fn scan_expr(
    expr: &ast::Expr,
    rel_display: &str,
    index: &LineIndex,
    config: &Config,
    findings: &mut Vec<Finding>,
) {
    match expr {
        ast::Expr::BoolOp(node) => {
            if matches!(node.op, ast::BoolOp::Or)
                && node.values.last().is_some_and(is_fallback_literal)
            {
                push_finding(findings, rel_display, index, expr, "or_default");
            }
        }
        ast::Expr::IfExp(node) => {
            if is_none_check(&node.test) {
                push_finding(findings, rel_display, index, expr, "ternary_none_else");
            }
        }
        ast::Expr::Call(node) => {
            if let ast::Expr::Attribute(func) = node.func.as_ref()
                && func.attr.as_str() == "get"
                && node.args.len() == 2
                && !is_none_constant(&node.args[1])
            {
                push_finding(findings, rel_display, index, expr, "dict_get_default");
            }
            if let ast::Expr::Name(func) = node.func.as_ref()
                && func.id.as_str() == "getattr"
                && node.args.len() == 3
            {
                push_finding(findings, rel_display, index, expr, "getattr_default");
            }
            if is_known_fallback_helper(call_name(&node.func), config) {
                push_finding(findings, rel_display, index, expr, "fallback_call");
            }
        }
        _ => {}
    }
}

fn is_none_check(expr: &ast::Expr) -> bool {
    match expr {
        ast::Expr::Compare(node) if node.ops.len() == 1 && node.comparators.len() == 1 => {
            matches!(node.ops[0], ast::CmpOp::Is | ast::CmpOp::IsNot)
                && is_none_constant(&node.comparators[0])
        }
        ast::Expr::UnaryOp(node) if matches!(node.op, ast::UnaryOp::Not) => {
            matches!(node.operand.as_ref(), ast::Expr::Name(_))
        }
        _ => false,
    }
}

fn is_fallback_literal(expr: &ast::Expr) -> bool {
    match expr {
        ast::Expr::Constant(ast::ExprConstant { value, .. }) => match value {
            ast::Constant::None | ast::Constant::Bool(false) => true,
            ast::Constant::Str(value) => value.is_empty(),
            ast::Constant::Int(value) => value.to_string() == "0",
            ast::Constant::Float(value) => *value == 0.0,
            _ => false,
        },
        ast::Expr::List(node) => node.elts.is_empty(),
        ast::Expr::Tuple(node) => node.elts.is_empty(),
        ast::Expr::Set(node) => node.elts.is_empty(),
        ast::Expr::Dict(node) => node.keys.is_empty(),
        _ => false,
    }
}

fn handler_is_importerror(handler: &ast::ExceptHandlerExceptHandler) -> bool {
    match handler.type_.as_deref() {
        None => true,
        Some(ast::Expr::Name(name)) => {
            matches!(name.id.as_str(), "ImportError" | "ModuleNotFoundError")
        }
        _ => false,
    }
}

fn handler_is_swallow(handler: &ast::ExceptHandlerExceptHandler) -> bool {
    let body = &handler.body;
    if body.is_empty() || body.iter().any(|stmt| matches!(stmt, ast::Stmt::Raise(_))) {
        return false;
    }
    if body.len() == 1 && matches!(body[0], ast::Stmt::Pass(_)) {
        return true;
    }
    match body.last() {
        Some(ast::Stmt::Return(node)) => node
            .value
            .as_deref()
            .is_none_or(|value| matches!(value, ast::Expr::Constant(_))),
        Some(ast::Stmt::Assign(_)) => true,
        _ => false,
    }
}

fn is_known_fallback_helper(name: Option<&str>, config: &Config) -> bool {
    let Some(name) = name else {
        return false;
    };
    config.fn_names.contains(name)
        || config
            .fn_prefixes
            .iter()
            .any(|prefix| name.starts_with(prefix))
}

fn push_finding<T: rustpython_parser::ast::Ranged>(
    findings: &mut Vec<Finding>,
    rel_display: &str,
    index: &LineIndex,
    node: &T,
    pattern: &'static str,
) {
    let (line, col) = index.line_col_for(node);
    findings.push(Finding {
        file: rel_display.to_string(),
        line,
        col,
        pattern,
        snippet: index.snippet_for(node),
    });
}

fn scan_fallback_comments(source: &str, rel_display: &str) -> Vec<Finding> {
    source
        .lines()
        .enumerate()
        .filter_map(|(idx, line)| {
            let comment_start = line.find('#')?;
            let comment = &line[comment_start..];
            if !comment.to_ascii_lowercase().contains("fallback") {
                return None;
            }
            Some(Finding {
                file: rel_display.to_string(),
                line: idx + 1,
                col: comment_start,
                pattern: "fallback_comment",
                snippet: line.trim().to_string(),
            })
        })
        .collect()
}

fn absolute_path(file_path: &str, project_root: &Path) -> PathBuf {
    let path = Path::new(file_path);
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        project_root.join(path)
    }
}

fn normalize_path(path: &Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| path.to_path_buf())
}
