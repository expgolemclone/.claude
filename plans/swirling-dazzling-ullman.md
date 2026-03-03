# Plan: espanso YAML pre-commit validation hook

## Context
`match/` 配下のespanso YAMLファイルに構文・構造エラーがあるままコミットされるのを防ぐため、`.hooks/pre-commit` にバリデーションhookを追加する。以前の pre-commit hook（commit 99bc07d で削除）はRust/Python/YAML全てを検証していたが、今回はespanso YAML検証に絞る。

## 作成ファイル

### 1. `.hooks/pre-commit` (シェルスクリプト)
オーケストレーター。以下を実行:

1. `git diff --cached --name-only --diff-filter=ACM -- 'match/*.yml'` でステージ済みYAMLを取得
2. `powershell-open.yml`（自動生成）を除外
3. ステージ済みのmatch YAMLが無ければスキップ（exit 0）
4. `yamllint` が無ければ `uv tool install yamllint` で自動インストール
5. `yamllint -c .yamllint.yml` で各ファイルをlint
6. `uv run --with pyyaml python scripts/validate_espanso_yaml.py` でespanso構造検証
7. いずれか失敗なら exit 1

### 2. `scripts/validate_espanso_yaml.py` (Python検証スクリプト)
espanso固有の構造チェック:

- **トップレベル `matches:` キーの存在確認**（リストであること）
- **各エントリに `trigger`（または `triggers`）が存在すること**
  - `trigger` は `:` で始まる文字列であること
- **各エントリに `replace`（または `form` / `image_path`）が存在すること**
- **重複トリガー検出**: `--match-dir` で指定した `match/` 全体をスキャンし、ステージファイルだけでなく既存ファイルとの重複も検出

引数: `--match-dir <path>` + ステージ済みファイルのリスト

PyYAML依存 → hookから `uv run --with pyyaml` で呼び出すことで解決

## 設定変更

```sh
git config core.hooksPath .hooks
chmod +x .hooks/pre-commit
```

## 除外対象
- `powershell-open.yml`: 自動生成ファイルのためスキップ（basename判定）

## 検証方法
```sh
# 1. matchファイルをステージしてhookを手動実行
git add match/base.yml
.hooks/pre-commit

# 2. 意図的にエラーを入れてhookが失敗することを確認
# 例: trigger を消す、重複triggerを追加する、YAML構文を壊す

# 3. 正常なコミットが通ることを確認
git commit -m "test"
```

## 対象ファイル一覧
| Action | Path |
|--------|------|
| Create | `.hooks/pre-commit` |
| Create | `scripts/validate_espanso_yaml.py` |
| Run    | `git config core.hooksPath .hooks` |
