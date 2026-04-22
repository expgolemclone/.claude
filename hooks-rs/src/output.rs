use serde_json::json;
use std::io::{self, Write};

pub fn block(reason: &str) {
    let msg = json!({"decision": "block", "reason": reason});
    let _ = writeln!(io::stdout(), "{}", msg);
}

pub fn stop(reason: &str) {
    let msg = json!({"decision": "stop", "reason": reason});
    let _ = writeln!(io::stdout(), "{}", msg);
}

pub fn pass() {
    // 何も出力しない = pass
}
