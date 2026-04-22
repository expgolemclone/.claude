use std::collections::HashSet;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

const TEXT_PAIRS: &[(&str, &str)] = &[
    ("color:\"clawd_body\"", "color:\"clawd_background\""),
    (
        "backgroundColor:\"clawd_body\"",
        "backgroundColor:\"clawd_background\"",
    ),
    ("claude:\"rgb(215,119,87)\"", "claude:\"rgb(0,0,0)\""),
    ("claude:\"rgb(255,153,51)\"", "claude:\"rgb(0,0,0)\""),
    ("claude:\"ansi:redBright\"", "claude:\"ansi:black\""),
    (
        "{bold:!0},\"Claude Code\")",
        "{bold:!0,color:\"clawd_background\"},\"Claude Code\")",
    ),
    ("{bold:!0},q6)", "{bold:!0,color:\"clawd_background\"},q6)"),
    (
        "bold:!0,color:\"claude\"},Y)",
        "bold:!0,color:\"clawd_background\"},Y)",
    ),
    (
        "createElement(T,null,Z5(P.text,D))",
        "createElement(T,{color:\"clawd_background\"},Z5(P.text,D))",
    ),
    (
        "createElement(T,{dimColor:!0,italic:!0},Z5(O,z))",
        "createElement(T,{color:\"clawd_background\"},Z5(O,z))",
    ),
    (
        "createElement(T,{dimColor:!0},Z5(w,z))",
        "createElement(T,{color:\"clawd_background\"},Z5(w,z))",
    ),
    (
        "color:\"error\",external:\"bypassPermissions\"",
        "color:\"cyan\",external:\"bypassPermissions\"",
    ),
];

const BIN_PAIRS: &[(&[u8], &[u8])] = &[
    (b"rgb(215,119,87)", b"rgb(000,000,00)"),
    (b"rgb(255,153,51)", b"rgb(000,000,00)"),
    (
        b"clawd_body:\"ansi:redBright\"",
        b"clawd_body:\"rgb(00,00,000)\"",
    ),
    (b"claude:\"ansi:redBright\"", b"claude:\"rgb(00,00,000)\""),
];

const WINDOWS_BIN_PAIRS: &[(&[u8], &[u8])] = &[
    (
        b"color:\"error\",external:\"bypassPermissions\"",
        b"color:\"cyan\", external:\"bypassPermissions\"",
    ),
    (
        b"A3.createElement(v,{bold:!0,color:\"claude\"},_)",
        b"A3.createElement(v,{bold:!0,color:\"black\" },_)",
    ),
    (b"let UH=Me8(q);if(", b"let UH=\"\"    ;if("),
    (b"let DH=Me8(q),OH=", b"let DH=\"\"    ,OH="),
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PatchOutcome {
    AlreadyPatched,
    Patched(usize),
    NoMatches,
}

fn binary_pairs_for_target(path: &Path) -> Vec<(&'static [u8], &'static [u8])> {
    let mut pairs = BIN_PAIRS.to_vec();
    if path
        .extension()
        .is_some_and(|suffix| suffix.to_string_lossy().eq_ignore_ascii_case("exe"))
    {
        pairs.extend_from_slice(WINDOWS_BIN_PAIRS);
    }
    for (old, new) in &pairs {
        assert_eq!(old.len(), new.len(), "binary patch must keep byte length");
    }
    pairs
}

fn dedupe_paths(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let mut seen = HashSet::new();
    let mut unique = Vec::new();
    for path in paths {
        let key = fs::canonicalize(&path).unwrap_or_else(|_| path.clone());
        if seen.insert(key) {
            unique.push(path);
        }
    }
    unique
}

fn managed_versions(base: &Path) -> Vec<PathBuf> {
    let Ok(read_dir) = fs::read_dir(base) else {
        return Vec::new();
    };
    let mut versions: Vec<PathBuf> = read_dir
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.join("claude.exe").is_file())
        .collect();
    versions.sort_by(|a, b| b.cmp(a));
    versions
        .into_iter()
        .map(|path| path.join("claude.exe"))
        .collect()
}

fn windows_npm_candidates(home: &Path) -> Vec<PathBuf> {
    let anthropic_root = home.join("AppData/Roaming/npm/node_modules/@anthropic-ai");
    let stable_root = anthropic_root.join("claude-code");
    let mut candidates = vec![
        stable_root.join("bin/claude.exe"),
        stable_root.join("node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe"),
        stable_root.join("node_modules/@anthropic-ai/claude-code-win32-arm64/claude.exe"),
    ];

    let mut managed_dirs: Vec<PathBuf> = fs::read_dir(&anthropic_root)
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .is_some_and(|name| name.to_string_lossy().starts_with(".claude-code-"))
        })
        .collect();
    managed_dirs.sort_by(|a, b| b.cmp(a));
    for dir in managed_dirs {
        candidates.push(dir.join("bin/claude.exe"));
        candidates.push(dir.join("node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe"));
        candidates.push(dir.join("node_modules/@anthropic-ai/claude-code-win32-arm64/claude.exe"));
    }
    dedupe_paths(candidates)
}

fn candidates_for(system: &str, home: &Path) -> Vec<PathBuf> {
    if system == "Windows" {
        let mut candidates = vec![home.join(".local/bin/claude.exe")];
        candidates.extend(managed_versions(
            &home.join("AppData/Roaming/Claude/claude-code"),
        ));
        candidates.extend(windows_npm_candidates(home));
        candidates
            .push(home.join("AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js"));
        return dedupe_paths(candidates);
    }

    vec![
        home.join(".local/share/claude/app/cli.js"),
        home.join(".local/bin/claude"),
        home.join(".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
    ]
}

pub fn find_targets_for(system: &str, home: &Path) -> Vec<PathBuf> {
    dedupe_paths(candidates_for(system, home))
        .into_iter()
        .filter(|path| path.exists())
        .filter(|path| !path.to_string_lossy().contains("/nix/store/"))
        .collect()
}

fn patch_text_content(content: &str) -> (PatchOutcome, String) {
    let pending: Vec<_> = TEXT_PAIRS
        .iter()
        .copied()
        .filter(|(old, _)| content.contains(old))
        .collect();
    let done: Vec<_> = TEXT_PAIRS
        .iter()
        .filter(|(old, new)| !content.contains(old) && content.contains(new))
        .collect();

    if pending.is_empty() && done.len() == TEXT_PAIRS.len() {
        return (PatchOutcome::AlreadyPatched, content.to_string());
    }
    if pending.is_empty() {
        return (PatchOutcome::NoMatches, content.to_string());
    }

    let mut total = 0;
    let mut patched = content.to_string();
    for (old, new) in pending {
        total += patched.matches(old).count();
        patched = patched.replace(old, new);
    }
    (PatchOutcome::Patched(total), patched)
}

fn patch_binary_content(data: &[u8], path: &Path) -> (PatchOutcome, Vec<u8>) {
    let pairs = binary_pairs_for_target(path);
    let pending: Vec<_> = pairs
        .iter()
        .copied()
        .filter(|(old, _)| contains_bytes(data, old))
        .collect();
    let done: Vec<_> = pairs
        .iter()
        .filter(|(old, new)| !contains_bytes(data, old) && contains_bytes(data, new))
        .collect();

    if pending.is_empty() && done.len() == pairs.len() {
        return (PatchOutcome::AlreadyPatched, data.to_vec());
    }
    if pending.is_empty() {
        return (PatchOutcome::NoMatches, data.to_vec());
    }

    let mut total = 0;
    let mut patched = data.to_vec();
    for (old, new) in pending {
        total += count_bytes(&patched, old);
        patched = replace_bytes(&patched, old, new);
    }
    (PatchOutcome::Patched(total), patched)
}

fn contains_bytes(data: &[u8], needle: &[u8]) -> bool {
    !needle.is_empty() && data.windows(needle.len()).any(|window| window == needle)
}

fn count_bytes(data: &[u8], needle: &[u8]) -> usize {
    if needle.is_empty() {
        return 0;
    }
    data.windows(needle.len())
        .filter(|window| *window == needle)
        .count()
}

fn replace_bytes(data: &[u8], from: &[u8], to: &[u8]) -> Vec<u8> {
    if from.is_empty() {
        return data.to_vec();
    }
    let mut output = Vec::with_capacity(data.len());
    let mut index = 0;
    while index < data.len() {
        if index + from.len() <= data.len() && &data[index..index + from.len()] == from {
            output.extend_from_slice(to);
            index += from.len();
        } else {
            output.push(data[index]);
            index += 1;
        }
    }
    output
}

pub fn patch_text(path: &Path) -> io::Result<PatchOutcome> {
    let content = fs::read_to_string(path)?;
    let (outcome, patched) = patch_text_content(&content);
    if matches!(outcome, PatchOutcome::Patched(_)) {
        fs::write(path, patched)?;
    }
    Ok(outcome)
}

pub fn patch_binary(path: &Path) -> io::Result<PatchOutcome> {
    let data = fs::read(path)?;
    let (outcome, patched) = patch_binary_content(&data, path);
    if matches!(outcome, PatchOutcome::Patched(_)) {
        write_binary(path, &patched)?;
    }
    Ok(outcome)
}

fn write_binary(path: &Path, data: &[u8]) -> io::Result<()> {
    match fs::write(path, data) {
        Ok(()) => Ok(()),
        Err(err) if err.kind() == io::ErrorKind::PermissionDenied => {
            let tmp = path.with_extension(format!(
                "{}tmp",
                path.extension()
                    .map(|ext| format!("{}.", ext.to_string_lossy()))
                    .unwrap_or_default()
            ));
            fs::write(&tmp, data)?;
            let old = path.with_extension(format!(
                "{}old",
                path.extension()
                    .map(|ext| format!("{}.", ext.to_string_lossy()))
                    .unwrap_or_default()
            ));
            let _ = fs::remove_file(&old);
            fs::rename(path, &old)?;
            fs::rename(tmp, path)?;
            Ok(())
        }
        Err(err) => Err(err),
    }
}

pub fn backup(path: &Path) -> io::Result<PathBuf> {
    let backup = path.with_extension(format!(
        "{}bak",
        path.extension()
            .map(|ext| format!("{}.", ext.to_string_lossy()))
            .unwrap_or_default()
    ));
    fs::copy(path, &backup)?;
    println!("バックアップ: {}", backup.display());
    Ok(backup)
}

pub fn restore(path: &Path) -> io::Result<bool> {
    let backup = path.with_extension(format!(
        "{}bak",
        path.extension()
            .map(|ext| format!("{}.", ext.to_string_lossy()))
            .unwrap_or_default()
    ));
    if !backup.exists() {
        return Ok(false);
    }
    write_binary(path, &fs::read(backup)?)?;
    Ok(true)
}

fn patch_one(target: &Path, do_restore: bool) -> io::Result<PatchOutcome> {
    if do_restore {
        return if restore(target)? {
            Ok(PatchOutcome::Patched(1))
        } else {
            Ok(PatchOutcome::NoMatches)
        };
    }

    let outcome = if target.extension().is_some_and(|ext| ext == "js") {
        let content = fs::read_to_string(target)?;
        let (outcome, patched) = patch_text_content(&content);
        if matches!(outcome, PatchOutcome::Patched(_)) {
            backup(target)?;
            let _ = patched;
            return patch_text(target);
        }
        outcome
    } else {
        let data = fs::read(target)?;
        let (outcome, patched) = patch_binary_content(&data, target);
        if matches!(outcome, PatchOutcome::Patched(_)) {
            backup(target)?;
            let _ = patched;
            return patch_binary(target);
        }
        outcome
    };
    Ok(outcome)
}

fn render_outcome(outcome: &PatchOutcome) -> &'static str {
    match outcome {
        PatchOutcome::AlreadyPatched => "既にパッチ済みです。",
        PatchOutcome::Patched(_) => "パッチ適用",
        PatchOutcome::NoMatches => "置換対象が見つかりません。",
    }
}

pub fn main(args: &[String]) -> i32 {
    let do_restore = args.iter().any(|arg| arg == "--restore");
    let system = match std::env::consts::OS {
        "windows" => "Windows",
        _ => "Linux",
    };
    let Some(home) = home::home_dir() else {
        eprintln!("home directory not found");
        return 1;
    };
    let targets = find_targets_for(system, &home);
    if targets.is_empty() {
        eprintln!("Claude Code のインストールが見つかりません。");
        return 1;
    }

    let mut ok = true;
    for target in targets {
        println!("対象: {}", target.display());
        match patch_one(&target, do_restore) {
            Ok(PatchOutcome::AlreadyPatched) => {
                println!("{}", render_outcome(&PatchOutcome::AlreadyPatched))
            }
            Ok(PatchOutcome::Patched(total)) if do_restore => {
                println!("復元しました: {}", target.display());
                let _ = total;
            }
            Ok(PatchOutcome::Patched(total)) => {
                println!("パッチ適用: {total} 箇所を置換しました。")
            }
            Ok(PatchOutcome::NoMatches) => {
                eprintln!("{}", render_outcome(&PatchOutcome::NoMatches));
                ok = false;
            }
            Err(err) => {
                eprintln!("{err}");
                ok = false;
            }
        }
    }
    if ok { 0 } else { 1 }
}

#[cfg(test)]
mod tests {
    use super::{PatchOutcome, find_targets_for, patch_binary, render_outcome};
    use std::fs;
    use std::path::Path;
    use tempfile::tempdir;

    #[test]
    fn find_targets_detects_windows_npm_installs() {
        for relative_path in [
            Path::new("AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
            Path::new(
                "AppData/Roaming/npm/node_modules/@anthropic-ai/.claude-code-tySWtmFC/bin/claude.exe",
            ),
        ] {
            let temp = tempdir().unwrap();
            let home = temp.path().join("home");
            let target = home.join(relative_path);
            fs::create_dir_all(target.parent().unwrap()).unwrap();
            fs::write(&target, []).unwrap();
            let targets = find_targets_for("Windows", &home);
            assert!(targets.contains(&target));
        }
    }

    #[test]
    fn patch_binary_applies_windows_specific_pairs() {
        let temp = tempdir().unwrap();
        let target = temp.path().join("claude.exe");
        fs::write(
            &target,
            [
                b"rgb(215,119,87)".as_slice(),
                b"color:\"error\",external:\"bypassPermissions\"",
                b"A3.createElement(v,{bold:!0,color:\"claude\"},_)",
                b"let UH=Me8(q);if(",
                b"let DH=Me8(q),OH=",
            ]
            .join(&b'\0'),
        )
        .unwrap();

        assert_eq!(patch_binary(&target).unwrap(), PatchOutcome::Patched(5));

        let data = fs::read(&target).unwrap();
        assert!(
            !data
                .windows(b"rgb(215,119,87)".len())
                .any(|window| window == b"rgb(215,119,87)")
        );
        assert!(
            data.windows(b"rgb(000,000,00)".len())
                .any(|window| window == b"rgb(000,000,00)")
        );
        assert!(
            !data
                .windows(b"color:\"error\",external:\"bypassPermissions\"".len())
                .any(|window| window == b"color:\"error\",external:\"bypassPermissions\"")
        );
        assert!(
            data.windows(b"color:\"cyan\", external:\"bypassPermissions\"".len())
                .any(|window| window == b"color:\"cyan\", external:\"bypassPermissions\"")
        );
        assert!(
            !data
                .windows(b"A3.createElement(v,{bold:!0,color:\"claude\"},_)".len())
                .any(|window| window == b"A3.createElement(v,{bold:!0,color:\"claude\"},_)")
        );
        assert!(
            data.windows(b"A3.createElement(v,{bold:!0,color:\"black\" },_)".len())
                .any(|window| window == b"A3.createElement(v,{bold:!0,color:\"black\" },_)")
        );
        assert!(
            !data
                .windows(b"let UH=Me8(q);if(".len())
                .any(|window| window == b"let UH=Me8(q);if(")
        );
        assert!(
            data.windows(b"let UH=\"\"    ;if(".len())
                .any(|window| window == b"let UH=\"\"    ;if(")
        );
        assert!(
            !data
                .windows(b"let DH=Me8(q),OH=".len())
                .any(|window| window == b"let DH=Me8(q),OH=")
        );
        assert!(
            data.windows(b"let DH=\"\"    ,OH=".len())
                .any(|window| window == b"let DH=\"\"    ,OH=")
        );
    }

    #[test]
    fn patch_binary_is_idempotent_with_windows_specific_pairs() {
        let temp = tempdir().unwrap();
        let target = temp.path().join("claude.exe");
        fs::write(
            &target,
            [
                b"rgb(000,000,00)".as_slice(),
                b"clawd_body:\"rgb(00,00,000)\"",
                b"claude:\"rgb(00,00,000)\"",
                b"color:\"cyan\", external:\"bypassPermissions\"",
                b"A3.createElement(v,{bold:!0,color:\"black\" },_)",
                b"let UH=\"\"    ;if(",
                b"let DH=\"\"    ,OH=",
            ]
            .join(&b'\0'),
        )
        .unwrap();

        let outcome = patch_binary(&target).unwrap();
        assert_eq!(outcome, PatchOutcome::AlreadyPatched);
        assert_eq!(render_outcome(&outcome), "既にパッチ済みです。");
    }
}
