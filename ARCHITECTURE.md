# Claude Code 設定リポジトリ構造

このリポジトリは Claude Code の設定とフック群を管理する。現在の実行経路は Rust 実装
(`hooks-rs`) が主で、Python スクリプト群は互換参照・比較用として残している。

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

### `hooks-rs/`
Rust 版 hook ランタイム。`claude-hooks` バイナリ 1 本に各 hook を subcommand として集約する。

- `setup`         : `settings.json` を生成
- `setup-claude`  : Claude Opus 向け `settings.json` を生成
- `patch-clawd-mascot` : Claude Code 外観パッチ
- 各 hook は `block-*`, `post-*`, `stop-*`, `warn-*` subcommand として実装

生成される `settings.json` は Python hook ファイルではなく、`hooks-rs/target/.../claude-hooks <subcommand>`
を参照する。

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
Claude Code の各ツール実行前後に動作する検証・補助スクリプトの Python 版実装。
Rust 実装の互換参照先として維持している。

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

### `hooks/structural_clone_core.py`
`warn-structural-duplicates.py` のコアロジック。ツリー構造 (`NormalizedNode`) に基づく
AST 正規化 → ベクトル化 (親→子辺) → IDF 加重コサイン類似度 → ツリー反単一化 (AU) 類似度
のパイプラインで構造重複関数を検出する。Rust 版 (`warn_structural_duplicates.rs`) は
同一アルゴリズムを再現している。

### `tests/benchmarks/structural_clone_core/`
Python / Rust hook の end-to-end 比較ベンチマーク。

- `compare_python_rust_hooks.py`: 同一 JSON 入力で両 hook を subprocess 実行し、
  総時間・ms/file・stop 件数・判定差分を出力。`public-apis` (全件) と `youtube-dl` (均等サンプル/全件) に対応。

### `scripts/`
通知スクリプト等のユーティリティ。`patch-clawd-mascot.py` は legacy 実装で、現在は
Rust の `patch-clawd-mascot` subcommand が主系。

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
hooks-rs setup-claude ────> hooks-rs setup ロジック
                      │
                      └──> .env (API キー等)
```

`setup_claude.py` は `.env` を参照しないため、API キーなしで実行可能。

## 開発フロー

1. フック追加・変更: Rust 実装 (`hooks-rs/src/`) を修正
2. 設定再生成: `cargo run --manifest-path hooks-rs/Cargo.toml -- setup`
3. Claude Opus 向け再生成: `cargo run --manifest-path hooks-rs/Cargo.toml -- setup-claude`
4. テスト: `cargo test --manifest-path hooks-rs/Cargo.toml`
5. コミット & プッシュ
