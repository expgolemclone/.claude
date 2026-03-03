# Plan: uv のインストール

## Context

pre-commit hook (`.githooks/pre-commit`) が `uv` コマンドに依存しているが、環境にインストールされていないため `uv: command not found` でコミットが失敗している。

## 手順

1. **uv をインストール**
   - Windows (MSYS2/Git Bash) 環境なので、PowerShell の公式インストーラーを使用:
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```
   - または `pip install uv` でもインストール可能

2. **インストール確認**
   - `uv --version` で動作確認

3. **コミットを再実行**
   - `git commit -m "fix:add qwen"` を再度実行し、pre-commit hook が通ることを確認

## 対象ファイル

- 変更なし（ツールのインストールのみ）

## 検証

- `uv --version` が正常に出力される
- `git commit` が pre-commit hook を通過する
