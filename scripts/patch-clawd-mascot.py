#!/usr/bin/env python3
"""Clawdマスコット非表示パッチ: cli.js / claude.exe を自動検出してパッチする."""

import argparse
import platform
import shutil
import sys
from pathlib import Path

# cli.js (テキスト) 用の置換ペア
TEXT_OLD = 'color:"clawd_body"'
TEXT_NEW = 'color:"clawd_background"'

# claude.exe (バイナリ) 用の同一バイト長置換ペア
# rgb(215,119,87) = オレンジ (15 bytes)
# rgb(000,000,00) = 黒       (15 bytes)
BIN_OLD = b"rgb(215,119,87)"
BIN_NEW = b"rgb(000,000,00)"


def _candidates() -> list[Path]:
    """OS ごとの候補パスを優先度順で返す."""
    home = Path.home()
    system = platform.system()

    if system == "Windows":
        return [
            home / ".local/bin/claude.exe",
            *_managed_versions(home / "AppData/Roaming/Claude/claude-code"),
        ]

    # Linux
    return [
        home / ".local/share/claude/app/cli.js",
        home / ".local/bin/claude",
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


def find_target() -> Path | None:
    """OS に応じて cli.js または claude.exe のパスを返す."""
    for path in _candidates():
        if not path.exists():
            continue
        # NixOS: /nix/store 配下は読み取り専用 → overlay で対応
        if "/nix/store/" in str(path.resolve()):
            print(
                "NixOS 環境です。overlay の postPatch で対応してください。",
                file=sys.stderr,
            )
            return None
        return path

    return None


def patch_text(path: Path) -> bool:
    """cli.js をテキスト置換でパッチする."""
    content = path.read_text(encoding="utf-8")

    if TEXT_NEW in content and TEXT_OLD not in content:
        print("既にパッチ済みです。")
        return True

    if TEXT_OLD not in content:
        print(f"置換対象が見つかりません: {TEXT_OLD}", file=sys.stderr)
        return False

    count = content.count(TEXT_OLD)
    patched = content.replace(TEXT_OLD, TEXT_NEW)
    path.write_text(patched, encoding="utf-8")
    print(f"パッチ適用: {count} 箇所を置換しました。")
    return True


def patch_binary(path: Path) -> bool:
    """claude.exe をバイナリ置換でパッチする."""
    data = path.read_bytes()

    if BIN_NEW in data and BIN_OLD not in data:
        print("既にパッチ済みです。")
        return True

    if BIN_OLD not in data:
        print(f"置換対象が見つかりません: {BIN_OLD!r}", file=sys.stderr)
        return False

    count = data.count(BIN_OLD)
    patched = data.replace(BIN_OLD, BIN_NEW)
    _write_binary(path, patched)
    print(f"パッチ適用: {count} 箇所を置換しました。")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Clawdマスコット非表示パッチ")
    parser.add_argument("--restore", action="store_true", help="バックアップから復元")
    args = parser.parse_args()

    target = find_target()
    if target is None:
        print("Claude Code のインストールが見つかりません。", file=sys.stderr)
        sys.exit(1)

    print(f"対象: {target}")

    if args.restore:
        ok = restore(target)
        sys.exit(0 if ok else 1)

    is_text = target.suffix == ".js"

    # 冪等チェック: 既にパッチ済みならバックアップ不要
    if is_text:
        content = target.read_text(encoding="utf-8")
        already = TEXT_NEW in content and TEXT_OLD not in content
    else:
        data = target.read_bytes()
        already = BIN_NEW in data and BIN_OLD not in data

    if already:
        print("既にパッチ済みです。")
        sys.exit(0)

    backup(target)

    if is_text:
        ok = patch_text(target)
    else:
        ok = patch_binary(target)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
