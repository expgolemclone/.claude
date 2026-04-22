use rustpython_parser::Parse;
use rustpython_parser::ast::{self, Ranged};

pub struct LineIndex<'a> {
    source: &'a str,
    line_starts: Vec<usize>,
}

impl<'a> LineIndex<'a> {
    pub fn new(source: &'a str) -> Self {
        let mut line_starts = vec![0];
        for (idx, byte) in source.bytes().enumerate() {
            if byte == b'\n' {
                line_starts.push(idx + 1);
            }
        }
        Self {
            source,
            line_starts,
        }
    }

    pub fn line_col_for<T: Ranged>(&self, node: &T) -> (usize, usize) {
        self.line_col_from_offset(node.start().to_usize())
    }

    pub fn line_for<T: Ranged>(&self, node: &T) -> usize {
        self.line_col_for(node).0
    }

    pub fn snippet_for<T: Ranged>(&self, node: &T) -> String {
        self.line_text(self.line_for(node)).trim().to_string()
    }

    pub fn line_text(&self, line: usize) -> &str {
        if line == 0 || line > self.line_starts.len() {
            return "";
        }
        let start = self.line_starts[line - 1];
        let end = self
            .line_starts
            .get(line)
            .copied()
            .unwrap_or(self.source.len());
        self.source[start..end].trim_end_matches(['\r', '\n'])
    }

    fn line_col_from_offset(&self, offset: usize) -> (usize, usize) {
        let idx = match self.line_starts.binary_search(&offset) {
            Ok(idx) => idx,
            Err(idx) => idx.saturating_sub(1),
        };
        (idx + 1, offset.saturating_sub(self.line_starts[idx]))
    }
}

pub fn parse_suite(source: &str, source_path: &str) -> Option<ast::Suite> {
    ast::Suite::parse(source, source_path).ok()
}

pub fn call_name(func: &ast::Expr) -> Option<&str> {
    match func {
        ast::Expr::Name(name) => Some(name.id.as_str()),
        ast::Expr::Attribute(attr) => Some(attr.attr.as_str()),
        _ => None,
    }
}

pub fn dotted_name(expr: &ast::Expr) -> Option<String> {
    match expr {
        ast::Expr::Name(name) => Some(name.id.to_string()),
        ast::Expr::Attribute(attr) => {
            dotted_name(&attr.value).map(|base| format!("{base}.{}", attr.attr))
        }
        _ => None,
    }
}

pub fn is_none_constant(expr: &ast::Expr) -> bool {
    matches!(
        expr,
        ast::Expr::Constant(ast::ExprConstant {
            value: ast::Constant::None,
            ..
        })
    )
}

pub fn is_numeric_constant(expr: &ast::Expr) -> Option<(f64, String)> {
    match expr {
        ast::Expr::Constant(ast::ExprConstant {
            value: ast::Constant::Int(value),
            ..
        }) => {
            let text = value.to_string();
            text.parse::<f64>().ok().map(|num| (num, text))
        }
        ast::Expr::Constant(ast::ExprConstant {
            value: ast::Constant::Float(value),
            ..
        }) => Some((*value, value.to_string())),
        _ => None,
    }
}

pub fn walk_suite<Fs, Fe, Fh>(
    suite: &ast::Suite,
    visit_stmt: &mut Fs,
    visit_expr: &mut Fe,
    visit_handler: &mut Fh,
) where
    Fs: FnMut(&ast::Stmt),
    Fe: FnMut(&ast::Expr),
    Fh: FnMut(&ast::ExceptHandlerExceptHandler),
{
    for stmt in suite {
        walk_stmt(stmt, visit_stmt, visit_expr, visit_handler);
    }
}

pub fn walk_stmt<Fs, Fe, Fh>(
    stmt: &ast::Stmt,
    visit_stmt: &mut Fs,
    visit_expr: &mut Fe,
    visit_handler: &mut Fh,
) where
    Fs: FnMut(&ast::Stmt),
    Fe: FnMut(&ast::Expr),
    Fh: FnMut(&ast::ExceptHandlerExceptHandler),
{
    visit_stmt(stmt);
    match stmt {
        ast::Stmt::FunctionDef(node) => {
            walk_arguments(&node.args, visit_expr);
            for expr in &node.decorator_list {
                walk_expr(expr, visit_expr);
            }
            if let Some(expr) = &node.returns {
                walk_expr(expr, visit_expr);
            }
            for tp in &node.type_params {
                walk_type_param(tp, visit_expr);
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::AsyncFunctionDef(node) => {
            walk_arguments(&node.args, visit_expr);
            for expr in &node.decorator_list {
                walk_expr(expr, visit_expr);
            }
            if let Some(expr) = &node.returns {
                walk_expr(expr, visit_expr);
            }
            for tp in &node.type_params {
                walk_type_param(tp, visit_expr);
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::ClassDef(node) => {
            for expr in &node.bases {
                walk_expr(expr, visit_expr);
            }
            for keyword in &node.keywords {
                walk_expr(&keyword.value, visit_expr);
            }
            for expr in &node.decorator_list {
                walk_expr(expr, visit_expr);
            }
            for tp in &node.type_params {
                walk_type_param(tp, visit_expr);
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::Return(node) => {
            if let Some(expr) = &node.value {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Stmt::Delete(node) => {
            for expr in &node.targets {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Stmt::Assign(node) => {
            for expr in &node.targets {
                walk_expr(expr, visit_expr);
            }
            walk_expr(&node.value, visit_expr);
        }
        ast::Stmt::TypeAlias(node) => {
            walk_expr(&node.name, visit_expr);
            for tp in &node.type_params {
                walk_type_param(tp, visit_expr);
            }
            walk_expr(&node.value, visit_expr);
        }
        ast::Stmt::AugAssign(node) => {
            walk_expr(&node.target, visit_expr);
            walk_expr(&node.value, visit_expr);
        }
        ast::Stmt::AnnAssign(node) => {
            walk_expr(&node.target, visit_expr);
            walk_expr(&node.annotation, visit_expr);
            if let Some(expr) = &node.value {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Stmt::For(node) => {
            walk_expr(&node.target, visit_expr);
            walk_expr(&node.iter, visit_expr);
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::AsyncFor(node) => {
            walk_expr(&node.target, visit_expr);
            walk_expr(&node.iter, visit_expr);
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::While(node) => {
            walk_expr(&node.test, visit_expr);
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::If(node) => {
            walk_expr(&node.test, visit_expr);
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::With(node) => {
            for item in &node.items {
                walk_expr(&item.context_expr, visit_expr);
                if let Some(expr) = &item.optional_vars {
                    walk_expr(expr, visit_expr);
                }
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::AsyncWith(node) => {
            for item in &node.items {
                walk_expr(&item.context_expr, visit_expr);
                if let Some(expr) = &item.optional_vars {
                    walk_expr(expr, visit_expr);
                }
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::Match(node) => {
            walk_expr(&node.subject, visit_expr);
            for case in &node.cases {
                if let Some(expr) = &case.guard {
                    walk_expr(expr, visit_expr);
                }
                walk_stmts(&case.body, visit_stmt, visit_expr, visit_handler);
            }
        }
        ast::Stmt::Raise(node) => {
            if let Some(expr) = &node.exc {
                walk_expr(expr, visit_expr);
            }
            if let Some(expr) = &node.cause {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Stmt::Try(node) => {
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            for handler in &node.handlers {
                walk_handler(handler, visit_stmt, visit_expr, visit_handler);
            }
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.finalbody, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::TryStar(node) => {
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
            for handler in &node.handlers {
                walk_handler(handler, visit_stmt, visit_expr, visit_handler);
            }
            walk_stmts(&node.orelse, visit_stmt, visit_expr, visit_handler);
            walk_stmts(&node.finalbody, visit_stmt, visit_expr, visit_handler);
        }
        ast::Stmt::Assert(node) => {
            walk_expr(&node.test, visit_expr);
            if let Some(expr) = &node.msg {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Stmt::Expr(node) => walk_expr(&node.value, visit_expr),
        ast::Stmt::Import(_)
        | ast::Stmt::ImportFrom(_)
        | ast::Stmt::Global(_)
        | ast::Stmt::Nonlocal(_)
        | ast::Stmt::Pass(_)
        | ast::Stmt::Break(_)
        | ast::Stmt::Continue(_) => {}
    }
}

pub fn walk_expr<Fe>(expr: &ast::Expr, visit_expr: &mut Fe)
where
    Fe: FnMut(&ast::Expr),
{
    visit_expr(expr);
    match expr {
        ast::Expr::BoolOp(node) => {
            for expr in &node.values {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::NamedExpr(node) => {
            walk_expr(&node.target, visit_expr);
            walk_expr(&node.value, visit_expr);
        }
        ast::Expr::BinOp(node) => {
            walk_expr(&node.left, visit_expr);
            walk_expr(&node.right, visit_expr);
        }
        ast::Expr::UnaryOp(node) => walk_expr(&node.operand, visit_expr),
        ast::Expr::Lambda(node) => {
            walk_arguments(&node.args, visit_expr);
            walk_expr(&node.body, visit_expr);
        }
        ast::Expr::IfExp(node) => {
            walk_expr(&node.test, visit_expr);
            walk_expr(&node.body, visit_expr);
            walk_expr(&node.orelse, visit_expr);
        }
        ast::Expr::Dict(node) => {
            for expr in node.keys.iter().flatten() {
                walk_expr(expr, visit_expr);
            }
            for expr in &node.values {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Set(node) => {
            for expr in &node.elts {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::ListComp(node) => {
            walk_expr(&node.elt, visit_expr);
            for comp in &node.generators {
                walk_comprehension(comp, visit_expr);
            }
        }
        ast::Expr::SetComp(node) => {
            walk_expr(&node.elt, visit_expr);
            for comp in &node.generators {
                walk_comprehension(comp, visit_expr);
            }
        }
        ast::Expr::DictComp(node) => {
            walk_expr(&node.key, visit_expr);
            walk_expr(&node.value, visit_expr);
            for comp in &node.generators {
                walk_comprehension(comp, visit_expr);
            }
        }
        ast::Expr::GeneratorExp(node) => {
            walk_expr(&node.elt, visit_expr);
            for comp in &node.generators {
                walk_comprehension(comp, visit_expr);
            }
        }
        ast::Expr::Await(node) => walk_expr(&node.value, visit_expr),
        ast::Expr::Yield(node) => {
            if let Some(expr) = &node.value {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::YieldFrom(node) => walk_expr(&node.value, visit_expr),
        ast::Expr::Compare(node) => {
            walk_expr(&node.left, visit_expr);
            for expr in &node.comparators {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Call(node) => {
            walk_expr(&node.func, visit_expr);
            for expr in &node.args {
                walk_expr(expr, visit_expr);
            }
            for keyword in &node.keywords {
                walk_expr(&keyword.value, visit_expr);
            }
        }
        ast::Expr::FormattedValue(node) => {
            walk_expr(&node.value, visit_expr);
            if let Some(expr) = &node.format_spec {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::JoinedStr(node) => {
            for expr in &node.values {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Attribute(node) => walk_expr(&node.value, visit_expr),
        ast::Expr::Subscript(node) => {
            walk_expr(&node.value, visit_expr);
            walk_expr(&node.slice, visit_expr);
        }
        ast::Expr::Starred(node) => walk_expr(&node.value, visit_expr),
        ast::Expr::List(node) => {
            for expr in &node.elts {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Tuple(node) => {
            for expr in &node.elts {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Slice(node) => {
            if let Some(expr) = &node.lower {
                walk_expr(expr, visit_expr);
            }
            if let Some(expr) = &node.upper {
                walk_expr(expr, visit_expr);
            }
            if let Some(expr) = &node.step {
                walk_expr(expr, visit_expr);
            }
        }
        ast::Expr::Constant(_) | ast::Expr::Name(_) => {}
    }
}

fn walk_stmts<Fs, Fe, Fh>(
    stmts: &[ast::Stmt],
    visit_stmt: &mut Fs,
    visit_expr: &mut Fe,
    visit_handler: &mut Fh,
) where
    Fs: FnMut(&ast::Stmt),
    Fe: FnMut(&ast::Expr),
    Fh: FnMut(&ast::ExceptHandlerExceptHandler),
{
    for stmt in stmts {
        walk_stmt(stmt, visit_stmt, visit_expr, visit_handler);
    }
}

fn walk_handler<Fs, Fe, Fh>(
    handler: &ast::ExceptHandler,
    visit_stmt: &mut Fs,
    visit_expr: &mut Fe,
    visit_handler: &mut Fh,
) where
    Fs: FnMut(&ast::Stmt),
    Fe: FnMut(&ast::Expr),
    Fh: FnMut(&ast::ExceptHandlerExceptHandler),
{
    match handler {
        ast::ExceptHandler::ExceptHandler(node) => {
            visit_handler(node);
            if let Some(expr) = &node.type_ {
                walk_expr(expr, visit_expr);
            }
            walk_stmts(&node.body, visit_stmt, visit_expr, visit_handler);
        }
    }
}

fn walk_arguments<Fe>(args: &ast::Arguments, visit_expr: &mut Fe)
where
    Fe: FnMut(&ast::Expr),
{
    for arg in args
        .posonlyargs
        .iter()
        .chain(&args.args)
        .chain(&args.kwonlyargs)
    {
        if let Some(expr) = &arg.def.annotation {
            walk_expr(expr, visit_expr);
        }
        if let Some(expr) = &arg.default {
            walk_expr(expr, visit_expr);
        }
    }
    if let Some(arg) = &args.vararg
        && let Some(expr) = &arg.annotation
    {
        walk_expr(expr, visit_expr);
    }
    if let Some(arg) = &args.kwarg
        && let Some(expr) = &arg.annotation
    {
        walk_expr(expr, visit_expr);
    }
}

fn walk_comprehension<Fe>(comp: &ast::Comprehension, visit_expr: &mut Fe)
where
    Fe: FnMut(&ast::Expr),
{
    walk_expr(&comp.target, visit_expr);
    walk_expr(&comp.iter, visit_expr);
    for expr in &comp.ifs {
        walk_expr(expr, visit_expr);
    }
}

fn walk_type_param<Fe>(type_param: &ast::TypeParam, visit_expr: &mut Fe)
where
    Fe: FnMut(&ast::Expr),
{
    if let ast::TypeParam::TypeVar(node) = type_param
        && let Some(expr) = &node.bound
    {
        walk_expr(expr, visit_expr);
    }
}
