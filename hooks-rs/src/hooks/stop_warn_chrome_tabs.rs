use crate::input::HookInput;
use crate::output::block;

const MEM_USAGE_THRESHOLD: f64 = 0.70;

fn parse_memory_usage_ratio(content: &str) -> f64 {
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
    parse_memory_usage_ratio(&content)
}

#[cfg(test)]
mod tests {
    use super::parse_memory_usage_ratio;

    #[test]
    fn computes_ratio_from_meminfo() {
        let content = "MemTotal:       1000 kB\nMemAvailable:    300 kB\n";
        assert!((parse_memory_usage_ratio(content) - 0.7).abs() < 1e-9);
    }

    #[test]
    fn returns_zero_when_total_missing() {
        assert_eq!(parse_memory_usage_ratio("MemAvailable: 300 kB\n"), 0.0);
    }

    #[test]
    fn returns_zero_for_invalid_numbers() {
        let content = "MemTotal: abc kB\nMemAvailable: 300 kB\n";
        assert_eq!(parse_memory_usage_ratio(content), 0.0);
    }

    #[test]
    fn ignores_extra_lines() {
        let content = "Other: 1\nMemTotal: 2000 kB\nFoo: 3\nMemAvailable: 1000 kB\n";
        assert!((parse_memory_usage_ratio(content) - 0.5).abs() < 1e-9);
    }
}
