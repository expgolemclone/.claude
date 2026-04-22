use crate::input::HookInput;
use crate::output::block;

const MEM_USAGE_THRESHOLD: f64 = 0.70;

pub fn run(input: &HookInput) {
    if input.stop_hook_active {
        return;
    }
    if input.permission_mode == "plan" {
        return;
    }

    let usage = read_memory_usage_ratio();
    if usage <= MEM_USAGE_THRESHOLD {
        return;
    }

    block(&format!(
        "システムメモリ使用率が {:.0}% です（上限 {:.0}%）。\nメモリ節約のため不要なタブ・ウィンドウを閉じてください。",
        usage * 100.0,
        MEM_USAGE_THRESHOLD * 100.0
    ));
}

fn read_memory_usage_ratio() -> f64 {
    let content = match std::fs::read_to_string("/proc/meminfo") {
        Ok(c) => c,
        Err(_) => return 0.0,
    };
    let mut total: i64 = 0;
    let mut available: i64 = 0;
    for line in content.lines() {
        if line.starts_with("MemTotal:") {
            total = line
                .split_whitespace()
                .nth(1)
                .and_then(|v| v.parse().ok())
                .unwrap_or(0);
        } else if line.starts_with("MemAvailable:") {
            available = line
                .split_whitespace()
                .nth(1)
                .and_then(|v| v.parse().ok())
                .unwrap_or(0);
        }
        if total > 0 && available > 0 {
            break;
        }
    }
    if total <= 0 {
        return 0.0;
    }
    (total - available) as f64 / total as f64
}
