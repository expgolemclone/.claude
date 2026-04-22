use regex::Regex;

use crate::input::HookInput;
use crate::output::block;

const PROHIBITED_PATTERNS: &[(&str, &str)] = &[
    (r"^def \w+_worker\(", "worker function definition"),
    (r"^import threading\b", "threading import"),
    (r"^\s*from threading import\b", "threading import"),
    (r"\bthreading\.Lock\b", "threading.Lock usage"),
    (r"\bstats_lock\b", "worker stats lock usage"),
    (r"\bcounter\[0\]", "worker progress counter usage"),
    (r"^\s*stats\[", "worker stats dict mutation"),
    (r#"\bprint\(f""#, "worker progress print"),
    (r"\bget_connection\(\)", "DB connection in datasource"),
    (
        r"\bupsert_financial_items_bulk\b",
        "DB bulk upsert in datasource",
    ),
    (r"\bupsert_price\b", "DB upsert_price in datasource"),
    (r"\bupsert_stock\b", "DB upsert_stock in datasource"),
    (
        r"\bThreadPoolExecutor\b",
        "ThreadPoolExecutor in datasource",
    ),
    (
        r"\bconcurrent\.futures\b",
        "concurrent.futures in datasource",
    ),
    (
        r"^\s*SELECT DISTINCT ticker FROM",
        "SQL query in datasource",
    ),
    (
        r"^\s*SELECT 1 FROM financial_items",
        "skip-check query in datasource",
    ),
];

const NOQA_TAG: &str = "# noqa: tracked-file";

fn is_tracked_datasource(file_path: &str) -> bool {
    let norm = file_path.replace('\\', "/");
    if !norm.contains("/datasources/") || !norm.ends_with(".py") {
        return false;
    }
    let Some(parent_dir) = std::path::Path::new(file_path).parent() else {
        return false;
    };
    parent_dir.join("cache_invalidation.py").is_file()
}

fn find_violations(source: &str) -> Vec<(usize, String, String)> {
    let compiled: Vec<(Regex, &str)> = PROHIBITED_PATTERNS
        .iter()
        .filter_map(|(p, r)| Regex::new(p).ok().map(|re| (re, *r)))
        .collect();

    let mut violations = Vec::new();
    for (i, line) in source.lines().enumerate() {
        if line.contains(NOQA_TAG) {
            continue;
        }
        for (re, reason) in &compiled {
            if re.is_match(line) {
                violations.push((i + 1, line.trim().to_string(), reason.to_string()));
                break;
            }
        }
    }
    violations
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if !is_tracked_datasource(file_path) {
        return;
    }

    let content = match std::fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => return,
    };

    let violations = find_violations(&content);
    if violations.is_empty() {
        return;
    }

    let details: Vec<String> = violations
        .iter()
        .take(5)
        .map(|(ln, text, reason)| format!("  L{ln}: {reason}: {text}"))
        .collect();
    let basename = std::path::Path::new(file_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or(file_path);

    block(&format!(
        "{basename} はキャッシュ無効化のハッシュ追跡対象ファイルです。\n\
         ワーカー制御・DB問い合わせ等のロジックを含めないでください:\n\
         {}\n\
         worker.py や db/repository.py に配置してください ({NOQA_TAG} で除外可)。",
        details.join("\n")
    ));
}
