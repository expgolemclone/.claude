# hooks-rs

Claude Code の hook システムを一つの Rust バイナリにまとめたプロジェクト。
`settings.json` の各 hook エントリからサブコマンドとして呼び出される。

## アーキテクチャ

```
stdin (JSON) → main.rs (dispatch) → hooks::xxx::run() → stdout (JSON / silent)
```

### 全体構成

```
hooks-rs/
├── Cargo.toml
└── src/
    ├── main.rs                 サブコマンドのルーティング
    ├── input.rs                stdin からの JSON 入力
    ├── output.rs               block / stop / pass の出力
    ├── setup.rs                settings.json の生成（Linux / Windows）
    ├── setup_claude.rs         Claude 用 settings.json の生成
    ├── patch_clawd_mascot.rs   Claude Code のマスコットカラー変更
    ├── git.rs                  git コマンドのユーティリティ
    ├── process.rs              タイムアウト付きサブプロセス実行
    ├── project_root.rs         プロジェクトルート / git ルートの探索
    ├── python_ast.rs           rustpython-parser による Python AST 操作
    ├── nix_protected.rs        NixOS 設定ファイルの保護パターン検知
    ├── transcript.rs           Claude の transcript (JSONL) 読み取り
    └── hooks/                  個別の hook 実装（38モジュール）
```

### 入出力プロトコル

Claude Code の hook プロトコルに従い、stdin から JSON を読み、stdout に JSON を返す。

**入力** (`input::HookInput`)：

```json
{
  "tool_name": "Edit",
  "tool_input": { "file_path": "...", "new_string": "..." },
  "stop_hook_active": false,
  "permission_mode": "bypassPermissions",
  "cwd": "/home/user/project",
  "transcript_path": "/tmp/..."
}
```

**出力** (`output` モジュール)：

| 関数    | 出力                                     | 意味             |
| ------- | ---------------------------------------- | ---------------- |
| `block` | `{"decision": "block", "reason": "..."}` | ツール実行を拒否 |
| `stop`  | `{"decision": "stop", "reason": "..."}`  | 会話ターンを停止 |
| `pass`  | （何も出力しない）                       | 許可・通過       |

### サブコマンドの起動

`main.rs` は第 1 引数をサブコマンド名として受け取り、対応する `run()` にディスパッチする。
3 つのユーティリティコマンド（`setup`, `setup-claude`, `patch-clawd-mascot`）は
stdin を読まずに独立して動作する。

```rust
match subcommand {
    "block-any-type" => hooks::block_any_type::run(&input),
    "stop-lint-edited-python" => hooks::stop_lint_edited_python::run(&input),
    // ...
}
```

## Hook 一覧

フックは Claude Code のライフサイクルに合わせて 3 種類に分類される。

### PreToolUse — ツール実行前のガード

ツールが実行される直前に呼ばれ、`block` で拒否できる。

| サブコマンド                            | 対象ツール  | 目的                                         |
| --------------------------------------- | ----------- | -------------------------------------------- |
| `block-settings-json-direct-edit`       | Edit, Write | `settings.json` の直接編集を禁止             |
| `block-protected-nix-config`            | Edit, Write | NixOS 設定の保護対象行の変更を禁止           |
| `block-non-python-hook-scripts`         | Edit, Write | Python 以外の hook スクリプトを禁止          |
| `block-any-type`                        | Edit, Write | `Any` 型（py/go/rs）の使用を禁止             |
| `block-setup-py-cfg`                    | Edit, Write | `setup.py` / `setup.cfg` の新規作成を禁止    |
| `block-manual-requirements-txt`         | Edit, Write | `requirements.txt` の手動編集を禁止          |
| `block-wildcard-versions`               | Edit, Write | 依存関係のワイルドカード版指定を禁止         |
| `block-missing-annotations`             | Edit, Write | Python 関数の型注釈欠落を禁止                |
| `block-unbounded-dependency`            | Edit, Write | バージョン上限なしの依存関係を禁止           |
| `block-platform-specific-scripts`       | Write, Bash | プラットフォーム固有スクリプトの作成を禁止   |
| `block-git-add-force-staging`           | Bash        | `git add -A` / `git add .` を禁止            |
| `block-git-commit-prohibited-keywords`  | Bash        | 禁止キーワードを含むコミットを防止           |
| `block-commit-without-verification`     | Bash        | 検証なしのコミットを禁止                     |
| `block-git-commit-protected-changes`    | Bash        | 保護対象ファイルのコミットを禁止             |
| `block-nixos-rebuild-protected-changes` | Bash        | NixOS 設定保護対象の `nixos-rebuild` を禁止  |
| `block-prohibited-python-toolchains`    | Bash        | 禁止された Python ツールチェーンの使用を防止 |
| `block-install-without-lock`            | Bash        | ロックファイルなしの `pip install` を禁止    |

### PostToolUse — ツール実行後のスキャンと通知

ツール実行後に呼ばれ、コード品質の検査や自動セットアップを行う。
`block` で後追い拒否、`stop` で警告表示が可能。

| サブコマンド                         | 対象ツール        | 目的                                              |
| ------------------------------------ | ----------------- | ------------------------------------------------- |
| `post-auto-setup`                    | Bash              | `git pull/commit` 時に `setup` を自動実行         |
| `post-verify-protected-nix-config`   | Edit, Write, Bash | NixOS 設定の保護状態を検証                        |
| `post-cargo-clippy-on-rs-edit`       | Edit, Write       | `.rs` ファイル編集後に clippy を実行              |
| `post-oxisym-scan`                   | Edit, Write       | oxisym によるシンボルスキャン                     |
| `warn-hardcoded-paths`               | Edit, Write       | ハードコードされたパスに警告                      |
| `warn-structural-duplicates`         | Edit, Write       | Python 関数の構造的クローンを検出                 |
| `warn-gitignore-not-whitelist`       | Edit, Write       | `.gitignore` がホワイトリスト形式でない場合に警告 |
| `block-magic-numbers`                | Edit, Write       | マジックナンバーのキーワード引数を検出            |
| `check-hotstring-conflicts`          | Edit, Write       | Hotkey キーワードの衝突を検出                     |
| `block-worker-in-tracked-datasource` | Edit, Write       | tracked datasource 内の worker 定義を禁止         |
| `block-scrape-interval`              | Edit, Write       | スクレイプ間隔の不適切な値を禁止                  |
| `post-scan-fallbacks`                | Edit, Write       | フォールバック値のスキャン                        |

### Stop — ターン終了時の最終チェック

Claude の会話ターンが終了する直前に呼ばれる。
未コミット変更の検出、リント、全ファイルスキャンなどが行われる。

| サブコマンド                       | タイムアウト | 目的                                         |
| ---------------------------------- | ------------ | -------------------------------------------- |
| `stop-lint-edited-python`          | 300s         | 編集された Python ファイルをリント           |
| `stop-require-git-commit-and-push` | 15s          | 未コミット・未プッシュの変更を検出           |
| `stop-require-source-verification` | 15s          | ソース検証を要求                             |
| `stop-scan-error-handling`         | 15s          | エラーハンドリングの不備をスキャン           |
| `stop-scan-any-type`               | 15s          | 全 Python ファイルから `Any` 型をスキャン    |
| `stop-warn-chrome-tabs`            | 15s          | Chrome タブ関連の警告                        |
| `stop-prompt-architecture-md`      | 15s          | ARCHITECTURE.md の更新を促す                 |
| `stop-update-and-patch-claude`     | 120s         | Claude Code のアップデートとマスコットパッチ |

## 共通モジュール

### `input.rs`

stdin から JSON を読み取り、`HookInput` 構造体にデシリアライズする。
`ToolInput` は `file_path` と `path` の両方をサポートし、
`file_path_resolved()` で空文字列の場合にフォールバックする。

### `output.rs`

3 種類の出力関数を提供する。`pass()` は何も出力しないことで許可を示す。

### `setup.rs`

`settings.json` を生成するコアモジュール。プラットフォームごとに異なる設定を構築する。

- **Linux**: hook コマンドはパスをクォートなしで出力。`deny: ["Agent"]`
- **Windows**: hook コマンドはパスをダブルクォートで出力。`deny: ["Task", "Agent"]`。
  Stop に PowerShell の `notify-complete.ps1` を含む

生成された JSON は `serde_json::to_string_pretty` で整形される。

### `setup_claude.rs`

Claude 専用の `settings.json` を生成するエントリポイント。
共通設定に `model` や `effortLevel` を追加する。

### `patch_clawd_mascot.rs`

Claude Code のマスコットカラーをパッチするユーティリティ。

- **テキストパッチ**: `.js` ファイル内の色定義文字列を置換
- **バイナリパッチ**: 実行可能ファイル内の RGB 値や ANSI カラーコードを置換
- Windows 版には固有のパッチペア（PowerShell 関連）を追加適用
- バックアップ（`.bak`）と復元（`--restore`）をサポート
- 冪等性：既にパッチ済みの場合は `AlreadyPatched` を返す

### `git.rs`

`git ls-files` によるトラック済みファイル一覧の取得や、
`git` サブコマンドの実行、引用符内文字列の除去を提供する。

### `process.rs`

`wait-timeout` クレートを使ったタイムアウト付きプロセス実行。
Stop フックの長時間実行コマンド（clippy や nixos-rebuild など）で使用される。

### `project_root.rs`

`Cargo.toml` や `.git` をマーカーとして上方向に検索し、
プロジェクトルートや git ルートを見つける。

### `python_ast.rs`

`rustpython-parser` を使った Python AST のパースとトラバーサル。
以下の機能を提供する。

- `LineIndex`: ソースコードの行番号 ↔ オフセット変換
- `walk_suite` / `walk_stmt` / `walk_expr`: AST ノードの再帰走査
- `call_name` / `dotted_name`: 関数呼び出し名の抽出
- `is_none_constant` / `is_numeric_constant`: リテラル判定

`block_magic_numbers` や `warn_structural_duplicates` で活用される。

### `nix_protected.rs`

`configuration.nix` の保護対象パターン（`sysusers.enable`, `mutableUsers`,
`hashedPassword` など）を正規表現で監視する。
diff テキストを解析して、保護行の変更や `mkForce` による上書きを検出する。

### `transcript.rs`

Claude の transcript ファイル（JSONL 形式）を読み取り、
ツール使用履歴の抽出や最後のユーザーメッセージのインデックス特定を行う。

## 依存クレート

| クレート               | 用途                                |
| ---------------------- | ----------------------------------- |
| `serde` + `serde_json` | JSON のデシリアライズ・シリアライズ |
| `regex`                | 正規表現によるコードパターンマッチ  |
| `toml`                 | TOML 設定ファイルのパース           |
| `sha2`                 | ハッシュ計算                        |
| `home`                 | ホームディレクトリの取得            |
| `rustpython-parser`    | Python ソースコードの AST パース    |
| `wait-timeout`         | サブプロセスのタイムアウト制御      |

## テスト

各モジュールに `#[cfg(test)]` ブロックがあり、主に以下を検証している。

- 設定生成の構造とプラットフォーム差異（`setup.rs` のテスト群）
- hook コマンドの存在確認（`main.rs` のサブコマンドと設定の整合性）
- パターン検知の正確性（各フックの `check_*` / `find_*` 関数）
- `patch_clawd_mascot` の冪等性と Windows 固有ペアの適用
- 一時 git リポジトリを使った統合テスト

## 実行例

```sh
# settings.json の生成
./claude-hooks setup

# Claude 用 settings.json の生成
./claude-hooks setup-claude

# マスコットカラーのパッチ（復元は --restore）
./claude-hooks patch-clawd-mascot

# PreToolUse hook としての実行
echo '{"tool_name":"Edit","tool_input":{"file_path":"a.py","new_string":"x: Any = 1"}}' \
  | ./claude-hooks block-any-type
# => {"decision":"block","reason":"Any 型の使用は禁止されています..."}
```
