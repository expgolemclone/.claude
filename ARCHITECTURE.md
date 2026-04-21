# Claude Code 設定リポジトリ構造

このリポジトリは Claude Code の設定とフックスクリプトを管理する。

## 設定生成スクリプト

### `setup.py`
メインの設定生成スクリプト。OS 毎のフック構成を定義し、`settings.json` を生成する。

- **入力**: `.env` から API キー等を読み取り
- **出力**: `settings.json`
- **使用モデル**: `glm-5.1` (z.ai 経由)

```python
build_common_config()      # 共通設定（環境変数等）
build_linux_config()        # Linux 用フック構成
build_windows_config()      # Windows 用フック構成
```

`build_*_config()` は `common` 引数を受け取り、外部から設定を上書き可能。

### `setup_claude.py`
ネイティブ Claude Opus (`claude-opus-4-7`) 用の設定生成スクリプト。

`setup.py` からフック構成をインポートし、モデル・effortLevel 等を差し替える薄いラッパー。

```python
from setup import build_linux_config, build_windows_config

CLAUDE_COMMON = {
    "model": "claude-opus-4-7",
    "effortLevel": "xhigh",
    "skipDangerousModePermissionPrompt": True,
}

config = build_linux_config(common=CLAUDE_COMMON)  # または build_windows_config
```

**設計方針**: フック構成の変更は `setup.py` のみ行えばよい。`CLAUDE_COMMON` の値は `build_*_config()` 内の同名キーを上書きする。

## ディレクトリ構成

```
.claude/
├── hooks/          # フックスクリプト (PreToolUse/PostToolUse/Stop)
├── scripts/        # ユーティリティスクリプト
├── tests/          # フックのテスト
├── config/         # 設定ファイル
├── plans/          # plan mode の一時プランファイル置き場
└── projects/       # プロジェクト固有の設定
```

### `hooks/`
Claude Code の各ツール実行前後に動作する検証・補助スクリプト。

命名規則:
- `block-*.py`    : 操作をブロック
- `warn-*.py`     : 警告を表示
- `post-*.py`     : ツール実行後の処理
- `stop-*.py`     : セッション終了時の処理
- `inject-*.py`   : 設定注入
- `*_core.py`     : 検査ロジックの共通モジュール
- `git_utils.py`  : `git ls-files` ベースのファイル列挙ヘルパー

`stop-scan-*.py` は `git ls-files` で取得した管理下ファイルのみを検査対象とする。
ファイル列挙には `git_utils.git_tracked_files()` / `git_utils.git_tracked_py_files()` を使用する。

### `scripts/`
通知スクリプト等のユーティリティ。

- `patch-clawd-mascot.py`  : Claude Code 外観パッチ（Stop hook から自動呼出）
  - subprocess 呼出時は `errors="replace"` を指定（Windows cp932 環境での UnicodeDecodeError 防止）
  - タイムアウトは 120 秒（~250MB の claude.exe を read/backup/write するため）
  - `TEXT_PAIRS`: cli.js テキスト置換
    - `clawd_body` 色 → `clawd_background`（マスコット非表示）
    - `claude` 色トークン → 黒（ブランド文字・ロゴ非表示）
    - `bypassPermissions` 表示色 → 水色
  - `BIN_PAIRS`: claude.exe バイナリ同一バイト長置換
  - `WINDOWS_BIN_PAIRS`: Windows 向け追加バイナリ置換（bypass permissions 表示色、フィードタイトル黒化、Welcome back 空化）
- `notify-complete.ps1`    : Windows 用セッション完了通知

## 依存関係

```
setup_claude.py ──import──> setup.py
                      │
                      └──> .env (API キー等)
```

`setup_claude.py` は `.env` を参照しないため、API キーなしで実行可能。

## 開発フロー

1. フック追加・変更: `setup.py` の `build_*_config()` を修正
2. 動作確認: `python3 setup.py` または `python3 setup_claude.py`
3. テスト: `pytest tests/`
4. コミット & プッシュ
