use crate::input::HookInput;
use crate::output::block;
use crate::python_ast::{LineIndex, dotted_name, is_numeric_constant, parse_suite, walk_suite};
use regex::Regex;
use rustpython_parser::ast;
use std::fs;
use std::path::Path;
use toml::Value;

const MIN_INTERVAL: f64 = 1.0;

type SleepPattern = (&'static str, &'static str);

struct LangDef {
    http_re: &'static str,
    sleep_patterns: &'static [SleepPattern],
}

const RUST_SLEEP_PATTERNS: &[SleepPattern] = &[
    (r"Duration::from_secs\(\s*(\d+)", "s"),
    (r"Duration::from_secs_f(?:32|64)\(\s*([\d.]+)", "s"),
    (r"Duration::from_millis\(\s*(\d+)", "ms"),
];

const JS_TS_SLEEP_PATTERNS: &[SleepPattern] = &[
    (r"setTimeout\([^,]+,\s*(\d+)", "ms"),
    (r"(?:sleep|delay)\(\s*(\d+)", "ms"),
    (r"waitForTimeout\(\s*(\d+)", "ms"),
];

const DART_SLEEP_PATTERNS: &[SleepPattern] = &[
    (r"Duration\(\s*seconds:\s*(\d+)", "s"),
    (r"Duration\(\s*milliseconds:\s*(\d+)", "ms"),
];

const PYTHON_HTTP_RE: &str = r"\b(?:requests|httpx|session|client)\.(?:get|post|put|patch|delete|head|options|request|send)\b|\baiohttp\.ClientSession\b|\bpage\.goto\b|\burllib\.request\.urlopen\b";
const NOQA_RE: &str = r"(?:#|//)\s*noqa:\s*scrape-interval";

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() || !is_scrape_file(file_path) || is_test_file(file_path) {
        return;
    }

    let path = Path::new(file_path);
    if !path.is_file() {
        return;
    }

    let reason = match path.extension().and_then(|s| s.to_str()).unwrap_or("") {
        "toml" => check_toml(path),
        "py" => check_python(path),
        "rs" => check_regex_lang(path, rust_lang()),
        "js" | "ts" => check_regex_lang(path, js_ts_lang()),
        "dart" => check_regex_lang(path, dart_lang()),
        _ => None,
    };

    if let Some(reason) = reason {
        block(&reason);
    }
}

fn rust_lang() -> LangDef {
    LangDef {
        http_re: r"\breqwest::(?:get|Client)\b|\bclient\.(?:get|post|put|patch|delete|head|request)\(|\.send\(\)\.await\b|\bhyper::Client\b|\bsurf::(?:get|post|put|delete)\b",
        sleep_patterns: RUST_SLEEP_PATTERNS,
    }
}

fn js_ts_lang() -> LangDef {
    LangDef {
        http_re: r"\bfetch\(|\baxios\.(?:get|post|put|patch|delete|head|request)\(|\bgot\(|\bpage\.goto\(|\bky\.(?:get|post|put|patch|delete|head)\(",
        sleep_patterns: JS_TS_SLEEP_PATTERNS,
    }
}

fn dart_lang() -> LangDef {
    LangDef {
        http_re: r"\bhttp\.(?:get|post|put|patch|delete|head|read)\(|\bclient\.(?:get|post|put|patch|delete|head|send)\(|\bDio\(\)",
        sleep_patterns: DART_SLEEP_PATTERNS,
    }
}

fn check_toml(path: &Path) -> Option<String> {
    let basename = basename(path);
    let source = fs::read_to_string(path).ok()?;
    let data: Value = match toml::from_str(&source) {
        Ok(value) => value,
        Err(err) => {
            return Some(format!("{basename}: TOML を解析できません: {err}"));
        }
    };

    let Some(interval_value) = find_interval(&data) else {
        return Some(format!(
            "{basename}: interval キーが定義されていません。\nscrape設定には interval >= {MIN_INTERVAL}s を含めてください。"
        ));
    };
    let Some(seconds) = resolve_interval(interval_value) else {
        return Some(format!(
            "{basename}: interval の値を解析できません: {}",
            display_toml_value(interval_value)
        ));
    };
    if seconds < MIN_INTERVAL {
        return Some(format!(
            "{basename}: interval = {} ({seconds}s) は最低 {MIN_INTERVAL}s 未満です。",
            display_toml_value(interval_value)
        ));
    }
    None
}

fn find_interval(value: &Value) -> Option<&Value> {
    let Value::Table(table) = value else {
        return None;
    };
    if let Some(interval) = table.get("interval") {
        return Some(interval);
    }
    table.values().find_map(find_interval)
}

fn resolve_interval(value: &Value) -> Option<f64> {
    match value {
        Value::Integer(value) => Some(*value as f64),
        Value::Float(value) => Some(*value),
        Value::String(value) => parse_interval_str(value),
        _ => None,
    }
}

fn parse_interval_str(value: &str) -> Option<f64> {
    let value = value.trim();
    if let Some(ms) = value.strip_suffix("ms") {
        return ms.parse::<f64>().ok().map(|v| v / 1000.0);
    }
    if let Some(sec) = value.strip_suffix('s') {
        return sec.parse::<f64>().ok();
    }
    value.parse::<f64>().ok()
}

fn display_toml_value(value: &Value) -> String {
    match value {
        Value::String(value) => format!("{value:?}"),
        _ => value.to_string(),
    }
}

fn check_python(path: &Path) -> Option<String> {
    let source = fs::read_to_string(path).ok()?;
    let suite = parse_suite(&source, &path.display().to_string())?;
    let index = LineIndex::new(&source);
    let noqa_re = Regex::new(NOQA_RE).ok()?;
    let mut low_sleeps = Vec::new();
    let mut has_adequate_sleep = false;

    walk_suite(
        &suite,
        &mut |_| {},
        &mut |expr| {
            let ast::Expr::Call(call) = expr else {
                return;
            };
            let Some(func_name) = sleep_func_name(&call.func) else {
                return;
            };
            let Some(arg) = call.args.first() else {
                return;
            };
            let Some((value, _)) = is_numeric_constant(arg) else {
                return;
            };
            if value >= MIN_INTERVAL {
                has_adequate_sleep = true;
                return;
            }
            let line = index.line_for(expr);
            if noqa_re.is_match(index.line_text(line)) {
                return;
            }
            low_sleeps.push((line, func_name.to_string(), value));
        },
        &mut |_| {},
    );

    let basename = basename(path);
    if !low_sleeps.is_empty() {
        let details = low_sleeps
            .iter()
            .map(|(line, call, value)| format!("  L{line}: {call}({value})"))
            .collect::<Vec<_>>()
            .join("\n");
        return Some(format!(
            "{basename}: sleep の値が {MIN_INTERVAL}s 未満です。\n{details}\nリクエスト間隔を {MIN_INTERVAL}s 以上にしてください (# noqa: scrape-interval で除外可)。"
        ));
    }

    if has_http_regex(&source, PYTHON_HTTP_RE, &noqa_re) && !has_adequate_sleep {
        return Some(format!(
            "{basename}: HTTP呼び出しがありますが sleep >= {MIN_INTERVAL}s が見つかりません。\nリクエスト間隔を確保する sleep を追加してください (# noqa: scrape-interval で除外可)。"
        ));
    }
    None
}

fn sleep_func_name(func: &ast::Expr) -> Option<&'static str> {
    match dotted_name(func).as_deref() {
        Some("time.sleep") => Some("time.sleep"),
        Some("asyncio.sleep") => Some("asyncio.sleep"),
        Some("sleep") => Some("sleep"),
        _ => None,
    }
}

fn check_regex_lang(path: &Path, lang: LangDef) -> Option<String> {
    let source = fs::read_to_string(path).ok()?;
    let lines: Vec<&str> = source.lines().collect();
    let noqa_re = Regex::new(NOQA_RE).ok()?;
    let sleep_patterns = compile_sleep_patterns(lang.sleep_patterns);
    let basename = basename(path);

    let low_sleeps = find_low_sleeps_regex(&lines, &sleep_patterns, &noqa_re);
    if !low_sleeps.is_empty() {
        let details = low_sleeps
            .iter()
            .map(|(line, text)| format!("  L{line}: {text}"))
            .collect::<Vec<_>>()
            .join("\n");
        return Some(format!(
            "{basename}: sleep/delay の値が {MIN_INTERVAL}s 未満です。\n{details}\nリクエスト間隔を {MIN_INTERVAL}s 以上にしてください (// noqa: scrape-interval で除外可)。"
        ));
    }

    if has_http_regex(&source, lang.http_re, &noqa_re)
        && !has_adequate_sleep_regex(&lines, &sleep_patterns)
    {
        return Some(format!(
            "{basename}: HTTP呼び出しがありますが sleep >= {MIN_INTERVAL}s が見つかりません。\nリクエスト間隔を確保する sleep/delay を追加してください (// noqa: scrape-interval で除外可)。"
        ));
    }
    None
}

fn compile_sleep_patterns(patterns: &[SleepPattern]) -> Vec<(Regex, &'static str)> {
    patterns
        .iter()
        .filter_map(|(pattern, unit)| Regex::new(pattern).ok().map(|re| (re, *unit)))
        .collect()
}

fn find_low_sleeps_regex(
    lines: &[&str],
    patterns: &[(Regex, &'static str)],
    noqa_re: &Regex,
) -> Vec<(usize, String)> {
    let mut violations = Vec::new();
    for (idx, line) in lines.iter().enumerate() {
        if noqa_re.is_match(line) {
            continue;
        }
        for (pattern, unit) in patterns {
            let Some(caps) = pattern.captures(line) else {
                continue;
            };
            let Some(value) = caps.get(1).and_then(|m| m.as_str().parse::<f64>().ok()) else {
                continue;
            };
            let seconds = if *unit == "ms" { value / 1000.0 } else { value };
            if seconds < MIN_INTERVAL {
                violations.push((idx + 1, line.trim().to_string()));
                break;
            }
        }
    }
    violations
}

fn has_http_regex(source: &str, pattern: &str, noqa_re: &Regex) -> bool {
    let Ok(http_re) = Regex::new(pattern) else {
        return false;
    };
    source
        .lines()
        .any(|line| !noqa_re.is_match(line) && http_re.is_match(line))
}

fn has_adequate_sleep_regex(lines: &[&str], patterns: &[(Regex, &'static str)]) -> bool {
    lines.iter().any(|line| {
        patterns.iter().any(|(pattern, unit)| {
            pattern
                .captures(line)
                .and_then(|caps| caps.get(1).and_then(|m| m.as_str().parse::<f64>().ok()))
                .is_some_and(|value| {
                    let seconds = if *unit == "ms" { value / 1000.0 } else { value };
                    seconds >= MIN_INTERVAL
                })
        })
    })
}

fn is_scrape_file(file_path: &str) -> bool {
    let normalized = file_path.replace('\\', "/");
    normalized.contains("/scrape/") || normalized.starts_with("scrape/")
}

fn is_test_file(file_path: &str) -> bool {
    let normalized = file_path.replace('\\', "/");
    normalized.contains("/tests/")
        || Path::new(file_path)
            .file_name()
            .and_then(|s| s.to_str())
            .is_some_and(|name| name.starts_with("test_"))
}

fn basename(path: &Path) -> String {
    path.file_name()
        .and_then(|s| s.to_str())
        .unwrap_or_default()
        .to_string()
}
