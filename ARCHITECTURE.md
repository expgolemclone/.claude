# Claude Code 設定リポジトリ構造

このリポジトリは Claude Code の設定、ネイティブ skill、フック群を管理する。実行経路は
Rust 実装 (`hooks-rs`) に統一されている。

## 設定生成コマンド

### `hooks-rs setup`
メインの設定生成コマンド。OS ごとのフック構成を定義し、`settings.json` を生成する。
コーディング規約の提示は `config/*.toml` 注入ではなく、Claude Code が `skills/` を
ネイティブに読む方式に移行済み。

- **入力**: `.env` から API キー等を読み取り
- **出力**: `settings.json`
- **使用モデル**: `glm-5.1` (z.ai 経由)

```text
cargo run --manifest-path hooks-rs/Cargo.toml -- setup
```

### `hooks-rs/`
Rust 版 hook ランタイム。`claude-hooks` バイナリ 1 本に各 hook を subcommand として集約する。

- `setup`         : `settings.json` を生成
- `setup-claude`  : Claude Opus 向け `settings.json` を生成
- `patch-clawd-mascot` : Claude Code 外観パッチ
- 各 hook は `block-*`, `post-*`, `stop-*`, `warn-*` subcommand として実装

生成される `settings.json` は Python hook ファイルではなく、`hooks-rs/target/.../claude-hooks <subcommand>`
を参照する。

### `hooks-rs setup-claude`
ネイティブ Claude Opus (`claude-opus-4-7`) 用の設定生成コマンド。

```text
cargo run --manifest-path hooks-rs/Cargo.toml -- setup-claude
```

`hooks-rs/src/setup_claude.rs` は `hooks-rs/src/setup.rs` の共通ロジックを利用しつつ、
モデル・`effortLevel` などだけを上書きする。

**設計方針**: フック構成の変更は `hooks-rs/src/setup.rs` に集約する。Claude 固有の差分は
`hooks-rs/src/setup_claude.rs` の `claude_common()` だけで表現する。

## ディレクトリ構成

```
.claude/
├── hooks-rs/       # Rust hook ランタイムと設定生成
├── scripts/        # ユーティリティスクリプト
├── skills/         # Claude Code の personal skills (`SKILL.md`)
├── config/         # hook 用のランタイム設定 (`cli_defaults.toml`, `magic_numbers.toml`)
├── plans/          # plan mode の一時プランファイル置き場
└── projects/       # プロジェクト固有の設定
```

### `skills/`
Claude Code がネイティブに検出する personal skills。各ディレクトリに `SKILL.md` を置き、
リポジトリ共通規約、Git 運用、Python/Rust、Markdown の規約をここで管理する。

旧来の `config/common.toml` `git.toml` `py.toml` などの prompt 断片は廃止し、
Skill に統合した。

### `config/`
人間向けプロンプト断片ではなく、hook が機械的に読むランタイム設定を置く。

- `cli_defaults.toml`    : Python lint 実行コマンドの既定値
- `magic_numbers.toml`   : lint と構造重複検出の閾値

### `hooks-rs/src/hooks/`
Claude Code の各ツール実行前後に動作する検証・補助ロジック。
各 hook は subcommand として `hooks-rs/src/main.rs` から起動される。

命名規則:
- `block_*.rs`   : 操作をブロック
- `warn_*.rs`    : 警告を表示
- `post_*.rs`    : ツール実行後の処理
- `stop_*.rs`    : セッション終了時の処理。`stop_hook_active` で再トリガーを判別するが、常にスキャンすべき hook（`stop_scan_any_type` 等）はこのガードを skip する
- `mod.rs`       : hook モジュール登録

テストは各 `.rs` ファイル内の `#[cfg(test)]` で管理している。

`inject-extension-rules-toml` は廃止済みで、`PreToolUse` では block 系 hook のみを登録する。

### `hooks-rs/src/python_ast.rs`
Python ソースを Rust から解析するための補助モジュール。Python 実装を残すためではなく、
Python コード向け hook を Rust から実装するために使う。

### `scripts/`
通知スクリプト等のユーティリティ。外観パッチ本体は Rust の
`patch-clawd-mascot` subcommand が担当する。

- `notify-complete.ps1`    : Windows 用セッション完了通知

## 依存関係

```text
Claude Code native skills ───> skills/*/SKILL.md
hooks-rs setup-claude ───────> hooks-rs::setup::write_settings
hooks-rs setup ──────────────> hooks-rs::setup::write_settings ───> .env (API キー等)
```

`setup-claude` は `claude_common()` を直接渡すため、`.env` なしでも実行できる。

## 開発フロー

1. 規約変更: `skills/*/SKILL.md` を修正
2. フック追加・変更: Rust 実装 (`hooks-rs/src/`) を修正
3. 設定再生成: `cargo run --manifest-path hooks-rs/Cargo.toml -- setup`
4. Claude Opus 向け再生成: `cargo run --manifest-path hooks-rs/Cargo.toml -- setup-claude`
5. テスト: `cargo test --manifest-path hooks-rs/Cargo.toml`
6. `ARCHITECTURE.md` 更新後にコミット & プッシュ
