use crate::git::git_tracked_files;
use crate::input::HookInput;
use crate::output::stop;
use crate::project_root::find_git_root;
use crate::python_ast::{LineIndex, parse_suite};
use rustpython_parser::ast;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use toml::Value;

#[derive(Clone)]
struct NormalizedNode {
    label: String,
    children: Vec<NormalizedNode>,
}

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
    ast_node_count: usize,
    vector: HashMap<String, f64>,
    normalized_tree: NormalizedNode,
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

// -- entry point --

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

// -- config --

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

// -- core detection --

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
                && record.ast_node_count >= config.min_ast_node_count
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
    let label_weights = compute_label_weights(&term_idf);

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
            let au_similarity = anti_unification_similarity(
                &source.normalized_tree,
                &candidate.normalized_tree,
                &label_weights,
            );
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

// -- record parsing --

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
            ast::Stmt::With(node) => {
                collect_functions(&node.body, path, index, stack, records);
            }
            ast::Stmt::AsyncWith(node) => {
                collect_functions(&node.body, path, index, stack, records);
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
    let tree = normalize_function(args, body);
    let vector = build_vector(&tree);
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
        ast_node_count: tree_node_count(&tree),
        vector,
        normalized_tree: tree,
    });
}

// -- normalization (tree-based, matching Python's structural_clone_core) --

fn normalize_function(args: &ast::Arguments, body: &[ast::Stmt]) -> NormalizedNode {
    let label = "FunctionDef".to_string();
    let mut children = vec![normalize_arguments(args)];
    children.extend(
        body_without_docstring(body)
            .iter()
            .map(normalize_stmt),
    );
    NormalizedNode { label, children }
}

fn normalize_arguments(args: &ast::Arguments) -> NormalizedNode {
    let label = "arguments".to_string();
    let mut children: Vec<NormalizedNode> = Vec::new();

    // posonlyargs + args
    for arg in args.posonlyargs.iter().chain(&args.args) {
        children.push(normalize_arg_data(&arg.def));
    }
    // vararg
    if let Some(arg) = &args.vararg {
        children.push(normalize_arg_data(arg));
    }
    // kwonlyargs
    for arg in &args.kwonlyargs {
        children.push(normalize_arg_data(&arg.def));
    }
    // defaults (from positional args, in order)
    for arg in args.posonlyargs.iter().chain(&args.args) {
        if let Some(default) = &arg.default {
            children.push(normalize_expr(default));
        }
    }
    // kw_defaults (from kwonlyargs)
    for arg in &args.kwonlyargs {
        if let Some(default) = &arg.default {
            children.push(normalize_expr(default));
        }
    }
    // kwarg
    if let Some(arg) = &args.kwarg {
        children.push(normalize_arg_data(arg));
    }

    NormalizedNode { label, children }
}

fn normalize_arg_data(arg: &ast::Arg) -> NormalizedNode {
    let label = "arg".to_string();
    let children = arg
        .annotation
        .as_ref()
        .map(|ann| vec![normalize_expr(ann)])
        .unwrap_or_default();
    NormalizedNode { label, children }
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

fn normalize_stmt(stmt: &ast::Stmt) -> NormalizedNode {
    let label = stmt_label(stmt);
    let children = match stmt {
        ast::Stmt::FunctionDef(node) => {
            let mut ch = vec![normalize_arguments(&node.args)];
            ch.extend(
                body_without_docstring(&node.body)
                    .iter()
                    .map(normalize_stmt),
            );
            ch
        }
        ast::Stmt::AsyncFunctionDef(node) => {
            let mut ch = vec![normalize_arguments(&node.args)];
            ch.extend(
                body_without_docstring(&node.body)
                    .iter()
                    .map(normalize_stmt),
            );
            ch
        }
        ast::Stmt::ClassDef(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .bases
                .iter()
                .map(normalize_expr)
                .collect();
            ch.extend(node.keywords.iter().map(normalize_keyword));
            ch.extend(node.decorator_list.iter().map(normalize_expr));
            ch.extend(node.body.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::Return(node) => node
            .value
            .as_ref()
            .map(|e| vec![normalize_expr(e)])
            .unwrap_or_default(),
        ast::Stmt::Delete(node) => node
            .targets
            .iter()
            .map(normalize_expr)
            .collect(),
        ast::Stmt::Assign(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .targets
                .iter()
                .map(normalize_expr)
                .collect();
            ch.push(normalize_expr(&node.value));
            ch
        }
        ast::Stmt::TypeAlias(node) => {
            vec![normalize_expr(&node.name), normalize_expr(&node.value)]
        }
        ast::Stmt::AugAssign(node) => {
            vec![
                normalize_expr(&node.target),
                normalize_expr(&node.value),
            ]
        }
        ast::Stmt::AnnAssign(node) => {
            let mut ch = vec![
                normalize_expr(&node.target),
                normalize_expr(&node.annotation),
            ];
            if let Some(value) = &node.value {
                ch.push(normalize_expr(value));
            }
            ch
        }
        ast::Stmt::For(node) => {
            let mut ch = vec![
                normalize_expr(&node.target),
                normalize_expr(&node.iter),
            ];
            ch.extend(node.body.iter().map(normalize_stmt));
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::AsyncFor(node) => {
            let mut ch = vec![
                normalize_expr(&node.target),
                normalize_expr(&node.iter),
            ];
            ch.extend(node.body.iter().map(normalize_stmt));
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::While(node) => {
            let mut ch = vec![normalize_expr(&node.test)];
            ch.extend(node.body.iter().map(normalize_stmt));
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::If(node) => {
            let mut ch = vec![normalize_expr(&node.test)];
            ch.extend(node.body.iter().map(normalize_stmt));
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::With(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .items
                .iter()
                .map(normalize_with_item)
                .collect();
            ch.extend(node.body.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::AsyncWith(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .items
                .iter()
                .map(normalize_with_item)
                .collect();
            ch.extend(node.body.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::Match(node) => {
            let mut ch = vec![normalize_expr(&node.subject)];
            ch.extend(node.cases.iter().map(normalize_match_case));
            ch
        }
        ast::Stmt::Raise(node) => {
            let mut ch = Vec::new();
            if let Some(exc) = &node.exc {
                ch.push(normalize_expr(exc));
            }
            if let Some(cause) = &node.cause {
                ch.push(normalize_expr(cause));
            }
            ch
        }
        ast::Stmt::Try(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .body
                .iter()
                .map(normalize_stmt)
                .collect();
            for handler in &node.handlers {
                let ast::ExceptHandler::ExceptHandler(h) = handler;
                ch.push(normalize_except_handler(h));
            }
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch.extend(node.finalbody.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::TryStar(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .body
                .iter()
                .map(normalize_stmt)
                .collect();
            for handler in &node.handlers {
                let ast::ExceptHandler::ExceptHandler(h) = handler;
                ch.push(normalize_except_handler(h));
            }
            ch.extend(node.orelse.iter().map(normalize_stmt));
            ch.extend(node.finalbody.iter().map(normalize_stmt));
            ch
        }
        ast::Stmt::Assert(node) => {
            let mut ch = vec![normalize_expr(&node.test)];
            if let Some(msg) = &node.msg {
                ch.push(normalize_expr(msg));
            }
            ch
        }
        ast::Stmt::Expr(node) => vec![normalize_expr(&node.value)],
        ast::Stmt::Import(_)
        | ast::Stmt::ImportFrom(_)
        | ast::Stmt::Global(_)
        | ast::Stmt::Nonlocal(_)
        | ast::Stmt::Pass(_)
        | ast::Stmt::Break(_)
        | ast::Stmt::Continue(_) => Vec::new(),
    };
    NormalizedNode {
        label: label.to_string(),
        children,
    }
}

fn normalize_expr(expr: &ast::Expr) -> NormalizedNode {
    let label = expr_label(expr);
    let children = match expr {
        ast::Expr::BoolOp(node) => node.values.iter().map(normalize_expr).collect(),
        ast::Expr::NamedExpr(node) => {
            vec![
                normalize_expr(&node.target),
                normalize_expr(&node.value),
            ]
        }
        ast::Expr::BinOp(node) => {
            vec![
                normalize_expr(&node.left),
                normalize_expr(&node.right),
            ]
        }
        ast::Expr::UnaryOp(node) => vec![normalize_expr(&node.operand)],
        ast::Expr::Lambda(node) => {
            vec![normalize_arguments(&node.args), normalize_expr(&node.body)]
        }
        ast::Expr::IfExp(node) => {
            vec![
                normalize_expr(&node.test),
                normalize_expr(&node.body),
                normalize_expr(&node.orelse),
            ]
        }
        ast::Expr::Dict(node) => {
            let mut ch: Vec<NormalizedNode> = node
                .keys
                .iter()
                .flatten()
                .map(normalize_expr)
                .collect();
            ch.extend(node.values.iter().map(normalize_expr));
            ch
        }
        ast::Expr::Set(node) => node.elts.iter().map(normalize_expr).collect(),
        ast::Expr::ListComp(node) => {
            let mut ch = vec![normalize_expr(&node.elt)];
            ch.extend(
                node.generators
                    .iter()
                    .map(normalize_comprehension),
            );
            ch
        }
        ast::Expr::SetComp(node) => {
            let mut ch = vec![normalize_expr(&node.elt)];
            ch.extend(
                node.generators
                    .iter()
                    .map(normalize_comprehension),
            );
            ch
        }
        ast::Expr::DictComp(node) => {
            let mut ch = vec![
                normalize_expr(&node.key),
                normalize_expr(&node.value),
            ];
            ch.extend(
                node.generators
                    .iter()
                    .map(normalize_comprehension),
            );
            ch
        }
        ast::Expr::GeneratorExp(node) => {
            let mut ch = vec![normalize_expr(&node.elt)];
            ch.extend(
                node.generators
                    .iter()
                    .map(normalize_comprehension),
            );
            ch
        }
        ast::Expr::Await(node) => vec![normalize_expr(&node.value)],
        ast::Expr::Yield(node) => node
            .value
            .as_ref()
            .map(|e| vec![normalize_expr(e)])
            .unwrap_or_default(),
        ast::Expr::YieldFrom(node) => vec![normalize_expr(&node.value)],
        ast::Expr::Compare(node) => {
            let mut ch = vec![normalize_expr(&node.left)];
            ch.extend(node.comparators.iter().map(normalize_expr));
            ch
        }
        ast::Expr::Call(node) => {
            let mut ch: Vec<NormalizedNode> = node.args.iter().map(normalize_expr).collect();
            ch.extend(node.keywords.iter().map(normalize_keyword));
            ch
        }
        ast::Expr::FormattedValue(node) => {
            let mut ch = vec![normalize_expr(&node.value)];
            if let Some(spec) = &node.format_spec {
                ch.push(normalize_expr(spec));
            }
            ch
        }
        ast::Expr::JoinedStr(node) => node.values.iter().map(normalize_expr).collect(),
        ast::Expr::Attribute(node) => vec![normalize_expr(&node.value)],
        ast::Expr::Subscript(node) => {
            vec![
                normalize_expr(&node.value),
                normalize_expr(&node.slice),
            ]
        }
        ast::Expr::Starred(node) => vec![normalize_expr(&node.value)],
        ast::Expr::List(node) => node.elts.iter().map(normalize_expr).collect(),
        ast::Expr::Tuple(node) => node.elts.iter().map(normalize_expr).collect(),
        ast::Expr::Slice(node) => {
            let mut ch = Vec::new();
            if let Some(lower) = &node.lower {
                ch.push(normalize_expr(lower));
            }
            if let Some(upper) = &node.upper {
                ch.push(normalize_expr(upper));
            }
            if let Some(step) = &node.step {
                ch.push(normalize_expr(step));
            }
            ch
        }
        ast::Expr::Constant(_) | ast::Expr::Name(_) => Vec::new(),
    };
    NormalizedNode { label, children }
}

fn normalize_keyword(kw: &ast::Keyword) -> NormalizedNode {
    let label = format!(
        "kw[{}]",
        kw.arg
            .as_ref()
            .map_or("**", |arg| arg.as_str())
    );
    NormalizedNode {
        label,
        children: vec![normalize_expr(&kw.value)],
    }
}

fn normalize_with_item(item: &ast::WithItem) -> NormalizedNode {
    let label = "withitem".to_string();
    let mut children = vec![normalize_expr(&item.context_expr)];
    if let Some(vars) = &item.optional_vars {
        children.push(normalize_expr(vars));
    }
    NormalizedNode { label, children }
}

fn normalize_comprehension(comp: &ast::Comprehension) -> NormalizedNode {
    let label = "comprehension".to_string();
    let mut children = vec![
        normalize_expr(&comp.target),
        normalize_expr(&comp.iter),
    ];
    children.extend(comp.ifs.iter().map(normalize_expr));
    NormalizedNode { label, children }
}

fn normalize_except_handler(handler: &ast::ExceptHandlerExceptHandler) -> NormalizedNode {
    let label = "ExceptHandler".to_string();
    let mut children = Vec::new();
    if let Some(type_) = &handler.type_ {
        children.push(normalize_expr(type_));
    }
    children.extend(handler.body.iter().map(normalize_stmt));
    NormalizedNode { label, children }
}

fn normalize_match_case(case: &ast::MatchCase) -> NormalizedNode {
    let label = "match_case".to_string();
    let mut children = vec![normalize_pattern(&case.pattern)];
    if let Some(guard) = &case.guard {
        children.push(normalize_expr(guard));
    }
    children.extend(case.body.iter().map(normalize_stmt));
    NormalizedNode { label, children }
}

fn normalize_pattern(pattern: &ast::Pattern) -> NormalizedNode {
    match pattern {
        ast::Pattern::MatchValue(node) => NormalizedNode {
            label: "MatchValue".to_string(),
            children: vec![normalize_expr(&node.value)],
        },
        ast::Pattern::MatchSingleton(_) => NormalizedNode {
            label: "MatchSingleton".to_string(),
            children: vec![],
        },
        ast::Pattern::MatchSequence(node) => NormalizedNode {
            label: "MatchSequence".to_string(),
            children: node
                .patterns
                .iter()
                .map(normalize_pattern)
                .collect(),
        },
        ast::Pattern::MatchMapping(node) => {
            let mut children: Vec<NormalizedNode> = node
                .keys
                .iter()
                .map(normalize_expr)
                .collect();
            children.extend(node.patterns.iter().map(normalize_pattern));
            NormalizedNode {
                label: "MatchMapping".to_string(),
                children,
            }
        }
        ast::Pattern::MatchClass(node) => {
            let mut children = vec![normalize_expr(&node.cls)];
            children.extend(node.patterns.iter().map(normalize_pattern));
            children.extend(node.kwd_patterns.iter().map(normalize_pattern));
            NormalizedNode {
                label: "MatchClass".to_string(),
                children,
            }
        }
        ast::Pattern::MatchStar(_) => NormalizedNode {
            label: "MatchStar".to_string(),
            children: vec![],
        },
        ast::Pattern::MatchAs(node) => {
            let children = node
                .pattern
                .as_ref()
                .map(|p| vec![normalize_pattern(p)])
                .unwrap_or_default();
            NormalizedNode {
                label: "MatchAs".to_string(),
                children,
            }
        }
        ast::Pattern::MatchOr(node) => NormalizedNode {
            label: "MatchOr".to_string(),
            children: node
                .patterns
                .iter()
                .map(normalize_pattern)
                .collect(),
        },
    }
}

// -- labels --

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
        ast::Expr::Call(node) => format!("Call[{}]", call_target_label(&node.func)),
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

fn call_target_label(func: &ast::Expr) -> String {
    match func {
        ast::Expr::Name(name) => name.id.to_string(),
        ast::Expr::Attribute(attr) => attr.attr.to_string(),
        ast::Expr::Lambda(_) => "lambda".to_string(),
        _ => format!("{:?}", expr_variant_name(func)),
    }
}

fn expr_variant_name(expr: &ast::Expr) -> &'static str {
    match expr {
        ast::Expr::BoolOp(_) => "BoolOp",
        ast::Expr::NamedExpr(_) => "NamedExpr",
        ast::Expr::BinOp(_) => "BinOp",
        ast::Expr::UnaryOp(_) => "UnaryOp",
        ast::Expr::Lambda(_) => "Lambda",
        ast::Expr::IfExp(_) => "IfExp",
        ast::Expr::Dict(_) => "Dict",
        ast::Expr::Set(_) => "Set",
        ast::Expr::ListComp(_) => "ListComp",
        ast::Expr::SetComp(_) => "SetComp",
        ast::Expr::DictComp(_) => "DictComp",
        ast::Expr::GeneratorExp(_) => "GeneratorExp",
        ast::Expr::Await(_) => "Await",
        ast::Expr::Yield(_) => "Yield",
        ast::Expr::YieldFrom(_) => "YieldFrom",
        ast::Expr::Compare(_) => "Compare",
        ast::Expr::Call(_) => "Call",
        ast::Expr::FormattedValue(_) => "FormattedValue",
        ast::Expr::JoinedStr(_) => "JoinedStr",
        ast::Expr::Constant(_) => "Constant",
        ast::Expr::Attribute(_) => "Attribute",
        ast::Expr::Subscript(_) => "Subscript",
        ast::Expr::Starred(_) => "Starred",
        ast::Expr::Name(_) => "Name",
        ast::Expr::List(_) => "List",
        ast::Expr::Tuple(_) => "Tuple",
        ast::Expr::Slice(_) => "Slice",
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

// -- vector building (parent→child edges, matching Python) --

fn build_vector(node: &NormalizedNode) -> HashMap<String, f64> {
    let mut vector = HashMap::new();
    walk_vector(node, &mut vector);
    vector
}

fn walk_vector(node: &NormalizedNode, vector: &mut HashMap<String, f64>) {
    let node_term = format!("node:{}", node.label);
    *vector.entry(node_term).or_insert(0.0) += 1.0;
    for child in &node.children {
        let edge_term = format!("edge:{}->{}", node.label, child.label);
        *vector.entry(edge_term).or_insert(0.0) += 1.0;
        walk_vector(child, vector);
    }
}

fn tree_node_count(node: &NormalizedNode) -> usize {
    1 + node
        .children
        .iter()
        .map(tree_node_count)
        .sum::<usize>()
}

// -- anti-unification similarity (matching Python) --

fn anti_unification_similarity(
    left: &NormalizedNode,
    right: &NormalizedNode,
    label_weights: &HashMap<String, f64>,
) -> f64 {
    let total_size =
        weighted_tree_size(left, label_weights) + weighted_tree_size(right, label_weights);
    if total_size == 0.0 {
        return 0.0;
    }
    let cost = weighted_substitution_cost(left, right, label_weights);
    let similarity = 1.0 - (cost / total_size);
    similarity.max(0.0)
}

fn compute_label_weights(term_idf: &HashMap<String, f64>) -> HashMap<String, f64> {
    term_idf
        .iter()
        .filter(|(term, _)| term.starts_with("node:"))
        .map(|(term, weight)| (term.strip_prefix("node:").unwrap_or(term).to_string(), *weight))
        .collect()
}

fn weighted_tree_size(node: &NormalizedNode, weights: &HashMap<String, f64>) -> f64 {
    let weight = weights.get(&node.label).copied().unwrap_or(1.0);
    weight + node
        .children
        .iter()
        .map(|child| weighted_tree_size(child, weights))
        .sum::<f64>()
}

fn weighted_substitution_cost(
    left: &NormalizedNode,
    right: &NormalizedNode,
    weights: &HashMap<String, f64>,
) -> f64 {
    if left.label == right.label {
        return children_cost(&left.children, &right.children, weights);
    }
    if label_base(&left.label) == label_base(&right.label) {
        let label_cost = weights.get(&left.label).copied().unwrap_or(1.0)
            + weights.get(&right.label).copied().unwrap_or(1.0);
        return label_cost + children_cost(&left.children, &right.children, weights);
    }
    weighted_tree_size(left, weights) + weighted_tree_size(right, weights)
}

fn children_cost(
    left_children: &[NormalizedNode],
    right_children: &[NormalizedNode],
    weights: &HashMap<String, f64>,
) -> f64 {
    if left_children.len() == right_children.len() {
        return left_children
            .iter()
            .zip(right_children.iter())
            .map(|(lc, rc)| weighted_substitution_cost(lc, rc, weights))
            .sum();
    }
    let aligned = lcs_alignment(left_children, right_children);
    let mut cost = 0.0;
    for (lc, rc) in aligned {
        match (lc, rc) {
            (Some(l), Some(r)) => {
                cost += weighted_substitution_cost(l, r, weights);
            }
            (Some(l), None) => {
                cost += weighted_tree_size(l, weights);
            }
            (None, Some(r)) => {
                cost += weighted_tree_size(r, weights);
            }
            (None, None) => {}
        }
    }
    cost
}

fn lcs_alignment<'a>(
    left: &'a [NormalizedNode],
    right: &'a [NormalizedNode],
) -> Vec<(Option<&'a NormalizedNode>, Option<&'a NormalizedNode>)> {
    let n = left.len();
    let m = right.len();
    let mut dp = vec![vec![0usize; m + 1]; n + 1];
    for i in (0..n).rev() {
        for j in (0..m).rev() {
            dp[i][j] = if labels_match(&left[i].label, &right[j].label) {
                dp[i + 1][j + 1] + 1
            } else {
                dp[i + 1][j].max(dp[i][j + 1])
            };
        }
    }
    let mut result = Vec::new();
    let mut i = 0;
    let mut j = 0;
    while i < n && j < m {
        if labels_match(&left[i].label, &right[j].label) {
            result.push((Some(&left[i]), Some(&right[j])));
            i += 1;
            j += 1;
        } else if dp[i + 1][j] >= dp[i][j + 1] {
            result.push((Some(&left[i]), None));
            i += 1;
        } else {
            result.push((None, Some(&right[j])));
            j += 1;
        }
    }
    while i < n {
        result.push((Some(&left[i]), None));
        i += 1;
    }
    while j < m {
        result.push((None, Some(&right[j])));
        j += 1;
    }
    result
}

fn labels_match(a: &str, b: &str) -> bool {
    a == b || label_base(a) == label_base(b)
}

fn label_base(label: &str) -> &str {
    label
        .find('[')
        .map_or(label, |idx| &label[..idx])
}

// -- IDF / cosine --

fn compute_term_idf(records: &[FunctionRecord], idf_floor: f64) -> HashMap<String, f64> {
    let mut doc_freq: HashMap<String, usize> = HashMap::new();
    for record in records {
        for term in record.vector.keys() {
            *doc_freq.entry(term.clone()).or_insert(0) += 1;
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

// -- helpers --

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

#[cfg(test)]
mod tests {
    use super::{Config, NormalizedNode, detect_structural_duplicates, list_python_files, tree_node_count};
    use std::path::Path;
    use std::process::Command;
    use tempfile::tempdir;

    fn git(cwd: &Path, args: &[&str]) {
        let status = Command::new("git")
            .args(args)
            .current_dir(cwd)
            .status()
            .unwrap();
        assert!(status.success(), "git {:?} failed", args);
    }

    fn test_config() -> Config {
        Config {
            min_stmt_count: 1,
            min_ast_node_count: 20,
            shortlist_size: 8,
            max_report_items: 3,
            min_vector_similarity: 0.60,
            min_au_similarity: 0.82,
            min_stmt_ratio: 0.60,
            idf_floor: 1.0,
        }
    }

    #[test]
    fn list_python_files_includes_untracked_current_file() {
        let repo = tempdir().unwrap();
        git(repo.path(), &["init"]);
        git(repo.path(), &["config", "user.email", "test@example.com"]);
        git(repo.path(), &["config", "user.name", "Test"]);

        let tracked = repo.path().join("tracked.py");
        std::fs::write(&tracked, "def tracked() -> None:\n    pass\n").unwrap();
        git(repo.path(), &["add", "."]);
        git(repo.path(), &["commit", "-m", "init"]);

        let current = repo.path().join("current.py");
        std::fs::write(&current, "def current() -> None:\n    pass\n").unwrap();

        let files = list_python_files(repo.path(), &current);
        assert!(files.iter().any(|path| path.ends_with("current.py")));
        assert!(files.iter().any(|path| path.ends_with("tracked.py")));
    }

    #[test]
    fn detects_structural_duplicate_for_untracked_candidate() {
        let repo = tempdir().unwrap();
        git(repo.path(), &["init"]);
        git(repo.path(), &["config", "user.email", "test@example.com"]);
        git(repo.path(), &["config", "user.name", "Test"]);

        let alpha = repo.path().join("alpha.py");
        let beta = repo.path().join("beta.py");
        std::fs::write(
            &alpha,
            "def _cmd_fetch_prices(args: object) -> None:\n    pool = _resolve_proxy_pool(args)\n    conn = get_connection()\n    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n    dispatch_workers(tickers, pool, worker_fn=fetch_prices_worker, label='prices')\n",
        )
        .unwrap();
        std::fs::write(
            &beta,
            "def _run_scrape_workers(args: object, worker_fn: object, label: str) -> None:\n    pool = _resolve_proxy_pool(args)\n    conn = get_connection()\n    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n    dispatch_workers(tickers, pool, worker_fn=worker_fn, label=label)\n",
        )
        .unwrap();
        git(repo.path(), &["add", "."]);
        git(repo.path(), &["commit", "-m", "init"]);

        let gamma = repo.path().join("gamma.py");
        std::fs::write(
            &gamma,
            "def run_candidate(args: object, worker_fn: object, label: str) -> None:\n    pool = _resolve_proxy_pool(args)\n    conn = get_connection()\n    tickers = args.ticker if args.ticker else get_all_tickers(conn)\n    dispatch_workers(tickers, pool, worker_fn=worker_fn, label=label)\n",
        )
        .unwrap();

        let matches = detect_structural_duplicates(repo.path(), &gamma, &test_config());
        assert!(!matches.is_empty());
        let rendered = format!(
            "{} {}",
            matches[0].source.qualname, matches[0].candidate.qualname
        );
        assert!(rendered.contains("run_candidate"));
        assert!(rendered.contains("_run_scrape_workers"));
    }

    #[test]
    fn small_function_is_ignored_under_default_thresholds() {
        let repo = tempdir().unwrap();
        git(repo.path(), &["init"]);
        git(repo.path(), &["config", "user.email", "test@example.com"]);
        git(repo.path(), &["config", "user.name", "Test"]);

        let alpha = repo.path().join("alpha.py");
        let beta = repo.path().join("beta.py");
        std::fs::write(
            &alpha,
            "def one(value: int) -> int:\n    result = value + 1\n    return result\n",
        )
        .unwrap();
        std::fs::write(
            &beta,
            "def two(value: int) -> int:\n    result = value + 1\n    return result\n",
        )
        .unwrap();
        git(repo.path(), &["add", "."]);
        git(repo.path(), &["commit", "-m", "init"]);

        let gamma = repo.path().join("gamma.py");
        std::fs::write(
            &gamma,
            "def three(value: int) -> int:\n    result = value + 1\n    return result\n",
        )
        .unwrap();

        let matches = detect_structural_duplicates(repo.path(), &gamma, &test_config());
        assert!(matches.is_empty());
    }

    #[test]
    fn tree_node_count_matches_expected() {
        let tree = NormalizedNode {
            label: "FunctionDef".to_string(),
            children: vec![
                NormalizedNode {
                    label: "arguments".to_string(),
                    children: vec![NormalizedNode {
                        label: "arg".to_string(),
                        children: vec![],
                    }],
                },
                NormalizedNode {
                    label: "Return".to_string(),
                    children: vec![NormalizedNode {
                        label: "Name".to_string(),
                        children: vec![],
                    }],
                },
            ],
        };
        assert_eq!(tree_node_count(&tree), 5);
    }
}
