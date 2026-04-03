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


def find_target() -> Path | None:
    """OS に応じて cli.js または claude.exe のパスを返す."""
    system = platform.system()

    if system == "Linux":
        # NixOS: /nix/store 配下は読み取り専用 → overlay で対応
        cli = Path.home() / ".local/share/claude/app/cli.js"
        if cli.exists():
            if "/nix/store/" in str(cli.resolve()):
                print(
                    "NixOS 環境です。overlay の postPatch で対応してください。",
                    file=sys.stderr,
                )
                return None
            return cli

    elif system == "Windows":
        # マネージドインストール: %APPDATA%/Claude/claude-code/<version>/claude.exe
        base = Path.home() / "AppData/Roaming/Claude/claude-code"
        if base.is_dir():
            versions = sorted(base.iterdir(), reverse=True)
            for v in versions:
                exe = v / "claude.exe"
                if exe.is_file():
                    return exe

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
    path.write_bytes(patched)
    print(f"パッチ適用: {count} 箇所を置換しました。")
    return True


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
    shutil.copy2(bak, path)
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
