use crate::git::git_tracked_files;
use crate::input::HookInput;
use crate::output::stop;
use crate::project_root::find_git_root;
use crate::python_ast::{LineIndex, call_name, parse_suite};
use rustpython_parser::ast;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use toml::Value;

#[derive(Clone)]
struct Config {
    min_stmt_count: usize,
    min_ast_node_count: usize,
    shortlist_size: usize,
    max_report_items: usize,
    min_vector_similarity: f64,
    min_au_similarity: f64,
    min_stmt_ratio: f64,
    idf_floor: f64,
}

#[derive(Clone)]
struct FunctionRecord {
    path: PathBuf,
    qualname: String,
    line: usize,
    stmt_count: usize,
    labels: Vec<String>,
    vector: HashMap<String, f64>,
}

struct FunctionContext<'a> {
    path: &'a Path,
    index: &'a LineIndex<'a>,
    stack: &'a [String],
}

struct MatchResult {
    source: FunctionRecord,
    candidate: FunctionRecord,
    vector_similarity: f64,
    au_similarity: f64,
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !file_path.ends_with(".py") {
        return;
    }

    let current_file = match absolute_path(file_path) {
        Some(path) if path.is_file() => path,
        _ => return,
    };
    let repo_root = match current_file.parent().and_then(find_git_root) {
        Some(root) => root,
        None => return,
    };
    let config = match load_config() {
        Some(config) => config,
        None => return,
    };

    let matches = detect_structural_duplicates(&repo_root, &current_file, &config);
    if matches.is_empty() {
        return;
    }

    let lines = matches
        .iter()
        .map(|m| {
            format!(
                "  - {}:{} `{}` ~= {}:{} `{}` (vector={:.3}, au={:.3})",
                relative_path(&m.source.path, &repo_root),
                m.source.line,
                m.source.qualname,
                relative_path(&m.candidate.path, &repo_root),
                m.candidate.line,
                m.candidate.qualname,
                m.vector_similarity,
                m.au_similarity
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    stop(&format!(
        "構造的に重複した Python 関数候補が見つかりました。\n{lines}\n共通化または抽象化を検討してください。"
    ));
}

fn load_config() -> Option<Config> {
    let path = std::env::current_dir()
        .ok()?
        .join("config")
        .join("magic_numbers.toml");
    let source = fs::read_to_string(path).ok()?;
    let data: Value = toml::from_str(&source).ok()?;
    let section = data.get("structural_clone_hook")?.as_table()?;
    Some(Config {
        min_stmt_count: read_usize(section, "min_stmt_count")?,
        min_ast_node_count: read_usize(section, "min_ast_node_count")?,
        shortlist_size: read_usize(section, "shortlist_size")?,
        max_report_items: read_usize(section, "max_report_items")?,
        min_vector_similarity: read_f64(section, "min_vector_similarity")?,
        min_au_similarity: read_f64(section, "min_au_similarity")?,
        min_stmt_ratio: read_f64(section, "min_stmt_ratio")?,
        idf_floor: read_f64(section, "idf_floor")?,
    })
}

fn read_usize(section: &toml::map::Map<String, Value>, key: &str) -> Option<usize> {
    section
        .get(key)?
        .as_integer()
        .and_then(|v| v.try_into().ok())
}

fn read_f64(section: &toml::map::Map<String, Value>, key: &str) -> Option<f64> {
    let value = section.get(key)?;
    value
        .as_float()
        .or_else(|| value.as_integer().map(|v| v as f64))
}

fn detect_structural_duplicates(
    repo_root: &Path,
    current_file: &Path,
    config: &Config,
) -> Vec<MatchResult> {
    let current_records = parse_records(current_file);
    if current_records.is_empty() {
        return Vec::new();
    }

    let mut all_records = Vec::new();
    for path in list_python_files(repo_root, current_file) {
        all_records.extend(parse_records(&path));
    }

    let eligible = all_records
        .into_iter()
        .filter(|record| {
            record.stmt_count >= config.min_stmt_count
                && record.labels.len() >= config.min_ast_node_count
        })
        .collect::<Vec<_>>();
    let current_paths = current_records
        .iter()
        .map(|record| {
            (
                normalize_path(&record.path),
                record.qualname.clone(),
                record.line,
            )
        })
        .collect::<HashSet<_>>();
    let current_eligible = eligible
        .iter()
        .filter(|record| {
            current_paths.contains(&(
                normalize_path(&record.path),
                record.qualname.clone(),
                record.line,
            ))
        })
        .cloned()
        .collect::<Vec<_>>();
    if current_eligible.is_empty() {
        return Vec::new();
    }

    let term_idf = compute_term_idf(&eligible, config.idf_floor);
    let mut matches = Vec::new();
    for source in &current_eligible {
        let mut shortlist = eligible
            .iter()
            .filter(|candidate| !is_same_record(source, candidate))
            .filter(|candidate| stmt_ratio_ok(source, candidate, config.min_stmt_ratio))
            .filter_map(|candidate| {
                let similarity = cosine_similarity(&source.vector, &candidate.vector, &term_idf);
                (similarity >= config.min_vector_similarity).then_some((candidate, similarity))
            })
            .collect::<Vec<_>>();
        shortlist.sort_by(|left, right| compare_f64_desc(left.1, right.1));
        shortlist.truncate(config.shortlist_size);

        for (candidate, vector_similarity) in shortlist {
            let au_similarity = sequence_similarity(&source.labels, &candidate.labels);
            if au_similarity >= config.min_au_similarity {
                matches.push(MatchResult {
                    source: source.clone(),
                    candidate: candidate.clone(),
                    vector_similarity,
                    au_similarity,
                });
            }
        }
    }

    matches.sort_by(|left, right| {
        compare_f64_desc(left.au_similarity, right.au_similarity)
            .then(compare_f64_desc(
                left.vector_similarity,
                right.vector_similarity,
            ))
            .then_with(|| left.source.path.cmp(&right.source.path))
            .then(left.source.line.cmp(&right.source.line))
            .then_with(|| left.candidate.path.cmp(&right.candidate.path))
            .then(left.candidate.line.cmp(&right.candidate.line))
    });
    matches.truncate(config.max_report_items);
    matches
}

fn parse_records(path: &Path) -> Vec<FunctionRecord> {
    let Ok(source) = fs::read_to_string(path) else {
        return Vec::new();
    };
    let Some(suite) = parse_suite(&source, &path.display().to_string()) else {
        return Vec::new();
    };
    let index = LineIndex::new(&source);
    let mut records = Vec::new();
    collect_functions(&suite, path, &index, &mut Vec::new(), &mut records);
    records
}

fn collect_functions(
    stmts: &[ast::Stmt],
    path: &Path,
    index: &LineIndex,
    stack: &mut Vec<String>,
    records: &mut Vec<FunctionRecord>,
) {
    for stmt in stmts {
        match stmt {
            ast::Stmt::ClassDef(node) => {
                stack.push(node.name.to_string());
                collect_functions(&node.body, path, index, stack, records);
                stack.pop();
            }
            ast::Stmt::FunctionDef(node) => {
                let ctx = FunctionContext { path, index, stack };
                collect_function(ctx, &node.name, &node.args, &node.body, stmt, records);
                stack.push(node.name.to_string());
                collect_functions(&node.body, path, index, stack, records);
                stack.pop();
            }
            ast::Stmt::AsyncFunctionDef(node) => {
                let ctx = FunctionContext { path, index, stack };
                collect_function(ctx, &node.name, &node.args, &node.body, stmt, records);
                stack.push(node.name.to_string());
                collect_functions(&node.body, path, index, stack, records);
                stack.pop();
            }
            ast::Stmt::If(node) => {
                collect_functions(&node.body, path, index, stack, records);
                collect_functions(&node.orelse, path, index, stack, records);
            }
            ast::Stmt::For(node) => {
                collect_functions(&node.body, path, index, stack, records);
                collect_functions(&node.orelse, path, index, stack, records);
            }
            ast::Stmt::AsyncFor(node) => {
                collect_functions(&node.body, path, index, stack, records);
                collect_functions(&node.orelse, path, index, stack, records);
            }
            ast::Stmt::While(node) => {
                collect_functions(&node.body, path, index, stack, records);
                collect_functions(&node.orelse, path, index, stack, records);
            }
            ast::Stmt::With(node) => collect_functions(&node.body, path, index, stack, records),
            ast::Stmt::AsyncWith(node) => {
                collect_functions(&node.body, path, index, stack, records)
            }
            ast::Stmt::Try(node) => {
                collect_functions(&node.body, path, index, stack, records);
                for handler in &node.handlers {
                    let ast::ExceptHandler::ExceptHandler(handler) = handler;
                    collect_functions(&handler.body, path, index, stack, records);
                }
                collect_functions(&node.orelse, path, index, stack, records);
                collect_functions(&node.finalbody, path, index, stack, records);
            }
            ast::Stmt::TryStar(node) => {
                collect_functions(&node.body, path, index, stack, records);
                for handler in &node.handlers {
                    let ast::ExceptHandler::ExceptHandler(handler) = handler;
                    collect_functions(&handler.body, path, index, stack, records);
                }
                collect_functions(&node.orelse, path, index, stack, records);
                collect_functions(&node.finalbody, path, index, stack, records);
            }
            ast::Stmt::Match(node) => {
                for case in &node.cases {
                    collect_functions(&case.body, path, index, stack, records);
                }
            }
            _ => {}
        }
    }
}

fn collect_function(
    ctx: FunctionContext,
    name: &ast::Identifier,
    args: &ast::Arguments,
    body: &[ast::Stmt],
    stmt: &ast::Stmt,
    records: &mut Vec<FunctionRecord>,
) {
    let mut labels = vec!["FunctionDef".to_string()];
    append_arguments(args, &mut labels);
    for stmt in body_without_docstring(body) {
        append_stmt(stmt, &mut labels);
    }
    let vector = build_vector(&labels);
    let qualname = if ctx.stack.is_empty() {
        name.to_string()
    } else {
        format!("{}.{}", ctx.stack.join("."), name)
    };
    records.push(FunctionRecord {
        path: normalize_path(ctx.path),
        qualname,
        line: ctx.index.line_for(stmt),
        stmt_count: body_without_docstring(body).len(),
        labels,
        vector,
    });
}

fn body_without_docstring(body: &[ast::Stmt]) -> &[ast::Stmt] {
    if let Some(ast::Stmt::Expr(expr)) = body.first()
        && matches!(
            expr.value.as_ref(),
            ast::Expr::Constant(ast::ExprConstant {
                value: ast::Constant::Str(_),
                ..
            })
        )
    {
        &body[1..]
    } else {
        body
    }
}

fn append_arguments(args: &ast::Arguments, labels: &mut Vec<String>) {
    labels.push("arguments".to_string());
    for arg in args
        .posonlyargs
        .iter()
        .chain(&args.args)
        .chain(&args.kwonlyargs)
    {
        labels.push("arg".to_string());
        if let Some(default) = &arg.default {
            append_expr(default, labels);
        }
    }
    if args.vararg.is_some() {
        labels.push("arg".to_string());
    }
    if args.kwarg.is_some() {
        labels.push("arg".to_string());
    }
}

fn append_stmt(stmt: &ast::Stmt, labels: &mut Vec<String>) {
    labels.push(stmt_label(stmt).to_string());
    match stmt {
        ast::Stmt::FunctionDef(node) => {
            append_arguments(&node.args, labels);
            for stmt in body_without_docstring(&node.body) {
                append_stmt(stmt, labels);
            }
        }
        ast::Stmt::AsyncFunctionDef(node) => {
            append_arguments(&node.args, labels);
            for stmt in body_without_docstring(&node.body) {
                append_stmt(stmt, labels);
            }
        }
        ast::Stmt::ClassDef(node) => {
            for stmt in &node.body {
                append_stmt(stmt, labels);
            }
        }
        ast::Stmt::Return(node) => {
            if let Some(expr) = &node.value {
                append_expr(expr, labels);
            }
        }
        ast::Stmt::Assign(node) => {
            for target in &node.targets {
                append_expr(target, labels);
            }
            append_expr(&node.value, labels);
        }
        ast::Stmt::AugAssign(node) => {
            append_expr(&node.target, labels);
            append_expr(&node.value, labels);
        }
        ast::Stmt::AnnAssign(node) => {
            append_expr(&node.target, labels);
            if let Some(expr) = &node.value {
                append_expr(expr, labels);
            }
        }
        ast::Stmt::For(node) => {
            append_expr(&node.target, labels);
            append_expr(&node.iter, labels);
            append_stmts(&node.body, labels);
            append_stmts(&node.orelse, labels);
        }
        ast::Stmt::AsyncFor(node) => {
            append_expr(&node.target, labels);
            append_expr(&node.iter, labels);
            append_stmts(&node.body, labels);
            append_stmts(&node.orelse, labels);
        }
        ast::Stmt::While(node) => {
            append_expr(&node.test, labels);
            append_stmts(&node.body, labels);
            append_stmts(&node.orelse, labels);
        }
        ast::Stmt::If(node) => {
            append_expr(&node.test, labels);
            append_stmts(&node.body, labels);
            append_stmts(&node.orelse, labels);
        }
        ast::Stmt::With(node) => {
            for item in &node.items {
                append_expr(&item.context_expr, labels);
            }
            append_stmts(&node.body, labels);
        }
        ast::Stmt::AsyncWith(node) => {
            for item in &node.items {
                append_expr(&item.context_expr, labels);
            }
            append_stmts(&node.body, labels);
        }
        ast::Stmt::Raise(node) => {
            if let Some(expr) = &node.exc {
                append_expr(expr, labels);
            }
        }
        ast::Stmt::Try(node) => {
            append_stmts(&node.body, labels);
            for handler in &node.handlers {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                labels.push("ExceptHandler".to_string());
                append_stmts(&handler.body, labels);
            }
            append_stmts(&node.orelse, labels);
            append_stmts(&node.finalbody, labels);
        }
        ast::Stmt::TryStar(node) => {
            append_stmts(&node.body, labels);
            for handler in &node.handlers {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                labels.push("ExceptHandler".to_string());
                append_stmts(&handler.body, labels);
            }
            append_stmts(&node.orelse, labels);
            append_stmts(&node.finalbody, labels);
        }
        ast::Stmt::Assert(node) => append_expr(&node.test, labels),
        ast::Stmt::Expr(node) => append_expr(&node.value, labels),
        ast::Stmt::Match(node) => {
            append_expr(&node.subject, labels);
            for case in &node.cases {
                if let Some(guard) = &case.guard {
                    append_expr(guard, labels);
                }
                append_stmts(&case.body, labels);
            }
        }
        ast::Stmt::Delete(_)
        | ast::Stmt::TypeAlias(_)
        | ast::Stmt::Import(_)
        | ast::Stmt::ImportFrom(_)
        | ast::Stmt::Global(_)
        | ast::Stmt::Nonlocal(_)
        | ast::Stmt::Pass(_)
        | ast::Stmt::Break(_)
        | ast::Stmt::Continue(_) => {}
    }
}

fn append_stmts(stmts: &[ast::Stmt], labels: &mut Vec<String>) {
    for stmt in stmts {
        append_stmt(stmt, labels);
    }
}

fn append_expr(expr: &ast::Expr, labels: &mut Vec<String>) {
    labels.push(expr_label(expr));
    match expr {
        ast::Expr::BoolOp(node) => {
            for expr in &node.values {
                append_expr(expr, labels);
            }
        }
        ast::Expr::NamedExpr(node) => {
            append_expr(&node.target, labels);
            append_expr(&node.value, labels);
        }
        ast::Expr::BinOp(node) => {
            append_expr(&node.left, labels);
            append_expr(&node.right, labels);
        }
        ast::Expr::UnaryOp(node) => append_expr(&node.operand, labels),
        ast::Expr::Lambda(node) => {
            append_arguments(&node.args, labels);
            append_expr(&node.body, labels);
        }
        ast::Expr::IfExp(node) => {
            append_expr(&node.test, labels);
            append_expr(&node.body, labels);
            append_expr(&node.orelse, labels);
        }
        ast::Expr::Dict(node) => {
            for expr in node.keys.iter().flatten() {
                append_expr(expr, labels);
            }
            for expr in &node.values {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Set(node) => {
            for expr in &node.elts {
                append_expr(expr, labels);
            }
        }
        ast::Expr::ListComp(node) => append_expr(&node.elt, labels),
        ast::Expr::SetComp(node) => append_expr(&node.elt, labels),
        ast::Expr::DictComp(node) => {
            append_expr(&node.key, labels);
            append_expr(&node.value, labels);
        }
        ast::Expr::GeneratorExp(node) => append_expr(&node.elt, labels),
        ast::Expr::Await(node) => append_expr(&node.value, labels),
        ast::Expr::Yield(node) => {
            if let Some(expr) = &node.value {
                append_expr(expr, labels);
            }
        }
        ast::Expr::YieldFrom(node) => append_expr(&node.value, labels),
        ast::Expr::Compare(node) => {
            append_expr(&node.left, labels);
            for expr in &node.comparators {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Call(node) => {
            for expr in &node.args {
                append_expr(expr, labels);
            }
            for keyword in &node.keywords {
                labels.push(format!(
                    "kw[{}]",
                    keyword.arg.as_ref().map_or("**", |arg| arg.as_str())
                ));
                append_expr(&keyword.value, labels);
            }
        }
        ast::Expr::FormattedValue(node) => append_expr(&node.value, labels),
        ast::Expr::JoinedStr(node) => {
            for expr in &node.values {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Attribute(node) => append_expr(&node.value, labels),
        ast::Expr::Subscript(node) => {
            append_expr(&node.value, labels);
            append_expr(&node.slice, labels);
        }
        ast::Expr::Starred(node) => append_expr(&node.value, labels),
        ast::Expr::List(node) => {
            for expr in &node.elts {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Tuple(node) => {
            for expr in &node.elts {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Slice(node) => {
            if let Some(expr) = &node.lower {
                append_expr(expr, labels);
            }
            if let Some(expr) = &node.upper {
                append_expr(expr, labels);
            }
            if let Some(expr) = &node.step {
                append_expr(expr, labels);
            }
        }
        ast::Expr::Constant(_) | ast::Expr::Name(_) => {}
    }
}

fn stmt_label(stmt: &ast::Stmt) -> &'static str {
    match stmt {
        ast::Stmt::FunctionDef(_) => "FunctionDef",
        ast::Stmt::AsyncFunctionDef(_) => "AsyncFunctionDef",
        ast::Stmt::ClassDef(_) => "ClassDef",
        ast::Stmt::Return(_) => "Return",
        ast::Stmt::Delete(_) => "Delete",
        ast::Stmt::Assign(_) => "Assign",
        ast::Stmt::TypeAlias(_) => "TypeAlias",
        ast::Stmt::AugAssign(_) => "AugAssign",
        ast::Stmt::AnnAssign(_) => "AnnAssign",
        ast::Stmt::For(_) => "For",
        ast::Stmt::AsyncFor(_) => "AsyncFor",
        ast::Stmt::While(_) => "While",
        ast::Stmt::If(_) => "If",
        ast::Stmt::With(_) => "With",
        ast::Stmt::AsyncWith(_) => "AsyncWith",
        ast::Stmt::Match(_) => "Match",
        ast::Stmt::Raise(_) => "Raise",
        ast::Stmt::Try(_) => "Try",
        ast::Stmt::TryStar(_) => "TryStar",
        ast::Stmt::Assert(_) => "Assert",
        ast::Stmt::Import(_) => "Import",
        ast::Stmt::ImportFrom(_) => "ImportFrom",
        ast::Stmt::Global(_) => "Global",
        ast::Stmt::Nonlocal(_) => "Nonlocal",
        ast::Stmt::Expr(_) => "Expr",
        ast::Stmt::Pass(_) => "Pass",
        ast::Stmt::Break(_) => "Break",
        ast::Stmt::Continue(_) => "Continue",
    }
}

fn expr_label(expr: &ast::Expr) -> String {
    match expr {
        ast::Expr::Name(_) => "Name".to_string(),
        ast::Expr::Attribute(node) => format!("Attr[{}]", node.attr),
        ast::Expr::Call(node) => format!("Call[{}]", call_name(&node.func).unwrap_or("Expr")),
        ast::Expr::BinOp(node) => format!("BinOp[{:?}]", node.op),
        ast::Expr::BoolOp(node) => format!("BoolOp[{:?}]", node.op),
        ast::Expr::UnaryOp(node) => format!("UnaryOp[{:?}]", node.op),
        ast::Expr::Compare(node) => format!(
            "Compare[{}]",
            node.ops
                .iter()
                .map(|op| format!("{op:?}"))
                .collect::<Vec<_>>()
                .join(",")
        ),
        ast::Expr::Constant(node) => constant_label(&node.value).to_string(),
        ast::Expr::NamedExpr(_) => "NamedExpr".to_string(),
        ast::Expr::Lambda(_) => "Lambda".to_string(),
        ast::Expr::IfExp(_) => "IfExp".to_string(),
        ast::Expr::Dict(_) => "Dict".to_string(),
        ast::Expr::Set(_) => "Set".to_string(),
        ast::Expr::ListComp(_) => "ListComp".to_string(),
        ast::Expr::SetComp(_) => "SetComp".to_string(),
        ast::Expr::DictComp(_) => "DictComp".to_string(),
        ast::Expr::GeneratorExp(_) => "GeneratorExp".to_string(),
        ast::Expr::Await(_) => "Await".to_string(),
        ast::Expr::Yield(_) => "Yield".to_string(),
        ast::Expr::YieldFrom(_) => "YieldFrom".to_string(),
        ast::Expr::FormattedValue(_) => "FormattedValue".to_string(),
        ast::Expr::JoinedStr(_) => "JoinedStr".to_string(),
        ast::Expr::Subscript(_) => "Subscript".to_string(),
        ast::Expr::Starred(_) => "Starred".to_string(),
        ast::Expr::List(_) => "List".to_string(),
        ast::Expr::Tuple(_) => "Tuple".to_string(),
        ast::Expr::Slice(_) => "Slice".to_string(),
    }
}

fn constant_label(value: &ast::Constant) -> &'static str {
    match value {
        ast::Constant::None => "Const[None]",
        ast::Constant::Bool(_) => "Const[Bool]",
        ast::Constant::Int(_) | ast::Constant::Float(_) | ast::Constant::Complex { .. } => {
            "Const[Num]"
        }
        ast::Constant::Str(_) => "Const[Str]",
        ast::Constant::Bytes(_) => "Const[Bytes]",
        _ => "Const[Other]",
    }
}

fn build_vector(labels: &[String]) -> HashMap<String, f64> {
    let mut vector = HashMap::new();
    for label in labels {
        *vector.entry(format!("node:{label}")).or_insert(0.0) += 1.0;
    }
    for pair in labels.windows(2) {
        *vector
            .entry(format!("edge:{}->{}", pair[0], pair[1]))
            .or_insert(0.0) += 1.0;
    }
    vector
}

fn compute_term_idf(records: &[FunctionRecord], idf_floor: f64) -> HashMap<String, f64> {
    let mut doc_freq = HashMap::new();
    for record in records {
        for term in record.vector.keys() {
            *doc_freq.entry(term.clone()).or_insert(0usize) += 1;
        }
    }
    let total_docs = records.len() as f64;
    doc_freq
        .into_iter()
        .map(|(term, freq)| {
            (
                term,
                ((total_docs + 1.0) / (freq as f64 + 1.0)).ln() + idf_floor,
            )
        })
        .collect()
}

fn cosine_similarity(
    left: &HashMap<String, f64>,
    right: &HashMap<String, f64>,
    term_idf: &HashMap<String, f64>,
) -> f64 {
    let norm = |vector: &HashMap<String, f64>| -> f64 {
        vector
            .iter()
            .map(|(term, value)| {
                let weighted = value * term_idf.get(term).copied().unwrap_or(1.0);
                weighted * weighted
            })
            .sum::<f64>()
    };
    let left_norm = norm(left);
    let right_norm = norm(right);
    if left_norm == 0.0 || right_norm == 0.0 {
        return 0.0;
    }
    let dot = left
        .iter()
        .filter_map(|(term, left_value)| {
            let right_value = right.get(term)?;
            let weight = term_idf.get(term).copied().unwrap_or(1.0);
            Some(left_value * right_value * weight * weight)
        })
        .sum::<f64>();
    dot / (left_norm.sqrt() * right_norm.sqrt())
}

fn sequence_similarity(left: &[String], right: &[String]) -> f64 {
    if left.is_empty() || right.is_empty() {
        return 0.0;
    }
    let lcs = lcs_len(left, right) as f64;
    (2.0 * lcs) / (left.len() as f64 + right.len() as f64)
}

fn lcs_len(left: &[String], right: &[String]) -> usize {
    let mut dp = vec![vec![0usize; right.len() + 1]; left.len() + 1];
    for i in (0..left.len()).rev() {
        for j in (0..right.len()).rev() {
            dp[i][j] = if labels_match(&left[i], &right[j]) {
                dp[i + 1][j + 1] + 1
            } else {
                dp[i + 1][j].max(dp[i][j + 1])
            };
        }
    }
    dp[0][0]
}

fn labels_match(left: &str, right: &str) -> bool {
    left == right || label_base(left) == label_base(right)
}

fn label_base(label: &str) -> &str {
    label.split_once('[').map_or(label, |(base, _)| base)
}

fn list_python_files(repo_root: &Path, current_file: &Path) -> Vec<PathBuf> {
    let mut files = git_tracked_files(repo_root, &["*.py"]);
    let current = normalize_path(current_file);
    if !files.iter().any(|path| normalize_path(path) == current) {
        files.push(current);
    }
    files
}

fn is_same_record(left: &FunctionRecord, right: &FunctionRecord) -> bool {
    left.path == right.path && left.qualname == right.qualname && left.line == right.line
}

fn stmt_ratio_ok(left: &FunctionRecord, right: &FunctionRecord, minimum: f64) -> bool {
    let larger = left.stmt_count.max(right.stmt_count);
    let smaller = left.stmt_count.min(right.stmt_count);
    larger != 0 && (smaller as f64 / larger as f64) >= minimum
}

fn compare_f64_desc(left: f64, right: f64) -> Ordering {
    right.partial_cmp(&left).unwrap_or(Ordering::Equal)
}

fn absolute_path(file_path: &str) -> Option<PathBuf> {
    let path = Path::new(file_path);
    if path.is_absolute() {
        Some(path.to_path_buf())
    } else {
        std::env::current_dir().ok().map(|cwd| cwd.join(path))
    }
}

fn normalize_path(path: &Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| path.to_path_buf())
}

fn relative_path(path: &Path, repo_root: &Path) -> String {
    path.strip_prefix(repo_root)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| {
            path.file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_string()
        })
}
