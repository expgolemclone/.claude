#!/usr/bin/env python3
"""Clawdマスコット非表示パッチ: cli.js / claude.exe を自動検出してパッチする."""

import argparse
import platform
import shutil
import sys
from pathlib import Path

# cli.js (テキスト) 用の置換ペア
TEXT_PAIRS = [
    ('color:"clawd_body"', 'color:"clawd_background"'),
    ('backgroundColor:"clawd_body"', 'backgroundColor:"clawd_background"'),
    # claude 色トークン（ブランドオレンジ）→ 黒
    ('claude:"rgb(215,119,87)"', 'claude:"rgb(0,0,0)"'),
    ('claude:"rgb(255,153,51)"', 'claude:"rgb(0,0,0)"'),
    ('claude:"ansi:redBright"', 'claude:"ansi:black"'),
    # バナータイトル「Claude Code」・Welcome back を背景色と同化
    ('{bold:!0},"Claude Code")', '{bold:!0,color:"clawd_background"},"Claude Code")'),
    ('{bold:!0},q6)', '{bold:!0,color:"clawd_background"},q6)'),
    # フィードタイトル (Tips / Recent activity 等) を背景色と同化
    ('bold:!0,color:"claude"},Y)', 'bold:!0,color:"clawd_background"},Y)'),
    # フィード本文・フッター・空メッセージを背景色と同化
    ('createElement(T,null,Z5(P.text,D))', 'createElement(T,{color:"clawd_background"},Z5(P.text,D))'),
    ('createElement(T,{dimColor:!0,italic:!0},Z5(O,z))', 'createElement(T,{color:"clawd_background"},Z5(O,z))'),
    ('createElement(T,{dimColor:!0},Z5(w,z))', 'createElement(T,{color:"clawd_background"},Z5(w,z))'),
    # bypass permissions 表示色 → 水色
    ('color:"error",external:"bypassPermissions"', 'color:"cyan",external:"bypassPermissions"'),
]

# claude.exe (バイナリ) 用の同一バイト長置換ペア [(old, new), ...]
BIN_PAIRS = [
    (b"rgb(215,119,87)", b"rgb(000,000,00)"),                          # clawd_body / claude RGB (15B)
    (b"rgb(255,153,51)", b"rgb(000,000,00)"),                          # claude RGB variant 2 (15B)
    (b'clawd_body:"ansi:redBright"', b'clawd_body:"rgb(00,00,000)"'),  # clawd_body ANSI (27B)
    (b'claude:"ansi:redBright"', b'claude:"rgb(00,00,000)"'),          # claude ANSI (23B)
]

# 現行 Windows の claude.exe bundle 向け追加置換
WINDOWS_BIN_PAIRS = [
    # bypass permissions 表示色 → 水色（空白で長さを合わせる）
    (
        b'color:"error",external:"bypassPermissions"',
        b'color:"cyan", external:"bypassPermissions"',
    ),
    # フィードタイトル (Tips / Recent activity 等) を黒化
    (
        b'A3.createElement(v,{bold:!0,color:"claude"},_)',
        b'A3.createElement(v,{bold:!0,color:"black" },_)',
    ),
    # Welcome back ヘッダは色属性を持たないため、描画文字列自体を空にする
    (b'let UH=Me8(q);if(', b'let UH=""    ;if('),
    (b'let DH=Me8(q),OH=', b'let DH=""    ,OH='),
]


def _binary_pairs_for_target(path: Path) -> list[tuple[bytes, bytes]]:
    """対象ファイルに応じたバイナリ置換ペアを返す."""
    pairs = list(BIN_PAIRS)
    if path.suffix.lower() == ".exe":
        pairs.extend(WINDOWS_BIN_PAIRS)

    for old, new in pairs:
        if len(old) != len(new):
            raise ValueError(f"binary patch must keep byte length: {old!r} -> {new!r}")

    return pairs


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    """同一パスを順序を保って一度だけ返す."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        key = path.resolve(strict=False)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _windows_npm_candidates(home: Path) -> list[Path]:
    """Windows の npm グローバル配下にある Claude Code 候補を返す."""
    anthropic_root = home / "AppData/Roaming/npm/node_modules/@anthropic-ai"
    stable_root = anthropic_root / "claude-code"

    candidates = [
        stable_root / "bin/claude.exe",
        stable_root / "node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe",
        stable_root / "node_modules/@anthropic-ai/claude-code-win32-arm64/claude.exe",
    ]

    if anthropic_root.is_dir():
        for pattern in (
            ".claude-code-*/bin/claude.exe",
            ".claude-code-*/node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe",
            ".claude-code-*/node_modules/@anthropic-ai/claude-code-win32-arm64/claude.exe",
        ):
            candidates.extend(sorted(anthropic_root.glob(pattern), reverse=True))

    return _dedupe_paths(candidates)


def _candidates() -> list[Path]:
    """OS ごとの候補パスを優先度順で返す."""
    home = Path.home()
    system = platform.system()

    if system == "Windows":
        return _dedupe_paths([
            home / ".local/bin/claude.exe",
            *_managed_versions(home / "AppData/Roaming/Claude/claude-code"),
            *_windows_npm_candidates(home),
            home / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js",
        ])

    # Linux
    return [
        home / ".local/share/claude/app/cli.js",
        home / ".local/bin/claude",
        home / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
    ]


def _managed_versions(base: Path) -> list[Path]:
    """マネージドインストールの全バージョンを降順で返す."""
    if not base.is_dir():
        return []
    return [
        v / "claude.exe"
        for v in sorted(base.iterdir(), reverse=True)
        if (v / "claude.exe").is_file()
    ]


def find_targets() -> list[Path]:
    """OS に応じて存在する全インストールパスを返す."""
    targets: list[Path] = []
    for path in _dedupe_paths(_candidates()):
        if not path.exists():
            continue
        # NixOS: /nix/store 配下は読み取り専用 → overlay で対応
        if "/nix/store/" in str(path.resolve()):
            print(
                "NixOS 環境です。overlay の postPatch で対応してください。",
                file=sys.stderr,
            )
            continue
        targets.append(path)
    return targets


def patch_text(path: Path) -> bool:
    """cli.js をテキスト置換でパッチする."""
    content = path.read_text(encoding="utf-8")

    pending = [(old, new) for old, new in TEXT_PAIRS if old in content]
    done = [new for old, new in TEXT_PAIRS if old not in content and new in content]

    if not pending and len(done) == len(TEXT_PAIRS):
        print("既にパッチ済みです。")
        return True

    if not pending:
        print("置換対象が見つかりません。", file=sys.stderr)
        return False

    total = 0
    for old, new in pending:
        total += content.count(old)
        content = content.replace(old, new)

    path.write_text(content, encoding="utf-8")
    print(f"パッチ適用: {total} 箇所を置換しました。")
    return True


def patch_binary(path: Path) -> bool:
    """claude.exe をバイナリ置換でパッチする."""
    data = path.read_bytes()
    pairs = _binary_pairs_for_target(path)

    pending = [(old, new) for old, new in pairs if old in data]
    done = [new for old, new in pairs if old not in data and new in data]

    if not pending and len(done) == len(pairs):
        print("既にパッチ済みです。")
        return True

    if not pending:
        print("置換対象が見つかりません。", file=sys.stderr)
        return False

    total = 0
    for old, new in pending:
        total += data.count(old)
        data = data.replace(old, new)

    _write_binary(path, data)
    print(f"パッチ適用: {total} 箇所を置換しました。")
    return True


def _write_binary(path: Path, data: bytes) -> None:
    """バイナリを書き込む。実行中exeはリネーム経由で回避する."""
    try:
        path.write_bytes(data)
    except PermissionError:
        # Windows: 実行中のexeは書き込み不可だがリネームは可能
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        old = path.with_suffix(path.suffix + ".old")
        # 前回の .old が実行中プロセスにロックされている場合があるため無視
        try:
            old.unlink(missing_ok=True)
        except PermissionError:
            print(f"警告: {old} の削除をスキップ（ロック中）")
        path.rename(old)
        tmp.rename(path)
        # .old は実行中プロセスが掴んでいるため削除せず残す
        print("(実行中のため、リネーム経由で置換しました)")


def backup(path: Path) -> Path:
    """パッチ前にバックアップを作成する."""
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"バックアップ: {bak}")
    return bak


def restore(path: Path) -> bool:
    """.bak からファイルを復元する."""
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        print(f"バックアップが見つかりません: {bak}", file=sys.stderr)
        return False
    _write_binary(path, bak.read_bytes())
    print(f"復元しました: {bak} → {path}")
    return True


def _patch_one(target: Path, *, do_restore: bool) -> bool:
    """1つのインストールをパッチまたは復元する."""
    print(f"対象: {target}")

    if do_restore:
        return restore(target)

    is_text = target.suffix == ".js"

    # 冪等チェック: 既にパッチ済みならバックアップ不要
    if is_text:
        content = target.read_text(encoding="utf-8")
        already = all(
            old not in content and new in content for old, new in TEXT_PAIRS
        )
    else:
        data = target.read_bytes()
        pairs = _binary_pairs_for_target(target)
        already = all(
            old not in data and new in data for old, new in pairs
        )

    if already:
        print("既にパッチ済みです。")
        return True

    backup(target)

    if is_text:
        return patch_text(target)
    return patch_binary(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clawdマスコット非表示パッチ")
    parser.add_argument("--restore", action="store_true", help="バックアップから復元")
    args = parser.parse_args()

    targets = find_targets()
    if not targets:
        print("Claude Code のインストールが見つかりません。", file=sys.stderr)
        sys.exit(1)

    ok = all(_patch_one(t, do_restore=args.restore) for t in targets)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
