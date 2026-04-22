use regex::Regex;

use crate::input::HookInput;
use crate::output::block;

const RETURN_EXEMPT: &[&str] = &["__init__", "__new__"];
const SELF_CLS: &[&str] = &["self", "cls"];

fn def_head_re() -> Regex {
    Regex::new(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(").unwrap()
}

fn return_arrow_re() -> Regex {
    Regex::new(r"\s*->").unwrap()
}

fn has_annotation(param: &str) -> bool {
    let mut depth: i32 = 0;
    for ch in param.chars() {
        match ch {
            '(' | '[' | '{' => depth += 1,
            ')' | ']' | '}' => depth -= 1,
            '=' if depth == 0 => return false,
            ':' if depth == 0 => return true,
            _ => {}
        }
    }
    false
}

fn param_name(param: &str) -> &str {
    let s = param.trim_start_matches('*');
    s.split('=')
        .next()
        .unwrap_or(s)
        .split(':')
        .next()
        .unwrap_or(s)
        .trim()
}

fn params_missing_annotation(params_str: &str) -> Vec<String> {
    let params_str = params_str.trim();
    if params_str.is_empty() {
        return Vec::new();
    }
    let mut missing = Vec::new();
    let mut depth: i32 = 0;
    let mut current = String::new();
    for ch in params_str.chars() {
        match ch {
            '(' | '[' | '{' => {
                depth += 1;
                current.push(ch);
            }
            ')' | ']' | '}' => {
                depth -= 1;
                current.push(ch);
            }
            ',' if depth == 0 => {
                check_param(current.trim(), &mut missing);
                current.clear();
            }
            _ => {
                current.push(ch);
            }
        }
    }
    if !current.trim().is_empty() {
        check_param(current.trim(), &mut missing);
    }
    missing
}

fn check_param(param: &str, missing: &mut Vec<String>) {
    if param.is_empty() || param == "/" || param == "*" {
        return;
    }
    let name = param_name(param).to_string();
    if SELF_CLS.contains(&name.as_str()) {
        return;
    }
    if param.starts_with('*') {
        if !name.is_empty() && !has_annotation(param) {
            missing.push(name);
        }
        return;
    }
    if !has_annotation(param) {
        missing.push(name);
    }
}

fn extract_def(lines: &[&str], start: usize) -> (String, String, Option<String>, usize) {
    let re = def_head_re();
    let mut combined = lines[start].to_string();
    let mut i = start;
    let mut depth = combined.chars().filter(|&c| c == '(').count() as i32
        - combined.chars().filter(|&c| c == ')').count() as i32;
    while depth > 0 && i + 1 < lines.len() {
        i += 1;
        combined.push(' ');
        combined.push_str(lines[i].trim());
        depth += lines[i].chars().filter(|&c| c == '(').count() as i32
            - lines[i].chars().filter(|&c| c == ')').count() as i32;
    }
    let head = re.captures(&combined);
    let func_name = head
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .unwrap_or_default();
    let paren_start = match combined.find('(') {
        Some(p) => p,
        None => return (func_name, String::new(), None, i),
    };
    let mut paren_depth: i32 = 0;
    let mut paren_end = paren_start;
    for (j, ch) in combined.char_indices().skip(paren_start) {
        match ch {
            '(' => paren_depth += 1,
            ')' => {
                paren_depth -= 1;
                if paren_depth == 0 {
                    paren_end = j;
                    break;
                }
            }
            _ => {}
        }
    }
    let params_str = combined[paren_start + 1..paren_end].to_string();
    let after_paren = combined[paren_end + 1..].trim();
    let trimmed = after_paren.trim_end_matches(':').trim();
    let return_annotation = if trimmed.is_empty() || !return_arrow_re().is_match(trimmed) {
        None
    } else {
        Some(trimmed.to_string())
    };
    (func_name, params_str, return_annotation, i)
}

fn check_def(func_name: &str, params_str: &str, return_annotation: Option<&str>) -> Option<String> {
    let missing = params_missing_annotation(params_str);
    if !missing.is_empty() {
        return Some(format!(
            "関数 `{func_name}` の引数 {} に型アノテーションがありません。",
            missing.join(", ")
        ));
    }
    if return_annotation.is_none() && !RETURN_EXEMPT.contains(&func_name) {
        return Some(format!(
            "関数 `{func_name}` に戻り値の型アノテーション（-> ...）がありません。"
        ));
    }
    None
}

fn check_python(text: &str) -> Option<String> {
    let lines: Vec<&str> = text.lines().collect();
    let re = def_head_re();
    let comment_re = Regex::new(r"^\s*#").unwrap();
    let mut i = 0;
    while i < lines.len() {
        if comment_re.is_match(lines[i]) {
            i += 1;
            continue;
        }
        if re.is_match(lines[i]) {
            let (func_name, params_str, return_annotation, end_line) = extract_def(&lines, i);
            if let Some(err) = check_def(&func_name, &params_str, return_annotation.as_deref()) {
                return Some(err);
            }
            i = end_line;
        }
        i += 1;
    }
    None
}

pub fn run(input: &HookInput) {
    let file_path = input.tool_input.file_path_resolved();
    if file_path.is_empty() || !file_path.ends_with(".py") {
        return;
    }

    let content = match input.tool_name.as_str() {
        "Edit" => input.tool_input.new_string.clone(),
        "Write" => input.tool_input.content.clone(),
        _ => return,
    };
    if content.is_empty() {
        return;
    }

    if let Some(reason) = check_python(&content) {
        block(&format!(
            "型アノテーションが不足しています（config: explicit_annotations = true）。\n{reason}"
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::check_python;

    #[test]
    fn blocks_missing_param_annotation() {
        let result = check_python("def foo(bar) -> None:\n    pass");
        assert!(result.is_some());
    }

    #[test]
    fn blocks_missing_return_annotation() {
        let result = check_python("def foo(bar: int):\n    pass");
        assert!(result.is_some());
    }

    #[test]
    fn allows_fully_annotated_function() {
        assert_eq!(check_python("def foo(bar: int) -> None:\n    pass"), None);
    }

    #[test]
    fn allows_init_without_return_annotation() {
        assert_eq!(
            check_python("def __init__(self, bar: int):\n    pass"),
            None
        );
    }

    #[test]
    fn blocks_multiline_missing_param_annotation() {
        let code = "def foo(\n    bar,\n    baz: str,\n) -> None:\n    pass\n";
        assert!(check_python(code).is_some());
    }

    #[test]
    fn allows_multiline_with_positional_only_marker() {
        let code = "def foo(\n    a: int,\n    /,\n    b: int,\n) -> None:\n    pass\n";
        assert_eq!(check_python(code), None);
    }

    #[test]
    fn blocks_tuple_default_without_annotation() {
        assert!(check_python("def foo(bar=(1, 2)) -> None:\n    pass").is_some());
    }

    #[test]
    fn allows_dict_default_with_annotation() {
        let code = "def foo(bar: dict[str, int] = {\"a\": 1}) -> None:\n    pass";
        assert_eq!(check_python(code), None);
    }
}
