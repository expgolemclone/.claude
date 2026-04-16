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


def _candidates() -> list[Path]:
    """OS ごとの候補パスを優先度順で返す."""
    home = Path.home()
    system = platform.system()

    if system == "Windows":
        return [
            home / ".local/bin/claude.exe",
            *_managed_versions(home / "AppData/Roaming/Claude/claude-code"),
            home / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js",
        ]

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
    for path in _candidates():
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

    pending = [(old, new) for old, new in BIN_PAIRS if old in data]
    done = [new for old, new in BIN_PAIRS if old not in data and new in data]

    if not pending and len(done) == len(BIN_PAIRS):
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
            pass
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
        already = all(
            old not in data and new in data for old, new in BIN_PAIRS
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
