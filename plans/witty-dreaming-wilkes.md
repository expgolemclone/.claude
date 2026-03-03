# Plan: pre-commit フックで denylist 違反 + エンコーディング変更の両方をブロックする

## Context

現在の `.hooks/pre-commit` は2つのチェックを実行するが、`check_encoding.py` は PostToolUse フック用（stdin JSON 入力）のため、pre-commit から直接呼ぶと JSON パースエラーで異常終了する。結果として意図しない形でコミットがブロックされている。

**目的:** denylist 違反とエンコーディング変更の両方を正しく検出・ブロックする pre-commit フックにする。

## 変更内容

### 1. `pre_commit_encoding.py` を新規作成 (`.hooks/pre_commit_encoding.py`)

pre-commit 用のエンコーディングチェックスクリプトを新規作成する。

- `git diff --cached --name-only --diff-filter=ACMR` で **ステージされたファイルのみ** を対象とする
- 対象拡張子: `.c`, `.h`, `.cpp`, `.hpp`
- HEAD 版のエンコーディング（`git show HEAD:<path>`）と作業ツリー版を比較
- `check_encoding.py` の `detect_encoding()` / `is_binary()` ロジックを再利用
- 違反があれば詳細を表示して exit 1

### 2. `.hooks/pre-commit` を修正

- `check_encoding.py` の呼び出しを `pre_commit_encoding.py` に変更
- typo 修正: "encording" → "encoding"

## 修正ファイル

| ファイル | 操作 |
|---|---|
| `.hooks/pre_commit_encoding.py` | 新規作成 |
| `.hooks/pre-commit` | 修正（呼び出し先変更） |

## 変更しないファイル

- `.hooks/check_encoding.py` — PostToolUse フック用としてそのまま維持
- `.hooks/pre_commit_denylist.py` — 変更不要（正しく動作している）
- `.hooks/.denylist` — 変更不要

## 検証方法（様々な文字コードでの体系的テスト）

プロジェクト実態: cp932 (1845 files) / utf-8 (5 files) のみ。EUC-JP 等は存在しない。

### テストケース一覧

| # | HEAD の encoding | staged の encoding | 期待結果 |
|---|---|---|---|
| 1 | cp932 | utf-8 | **ブロック** |
| 2 | utf-8 | cp932 | **ブロック** |
| 3 | cp932 | cp932 | 通過 |
| 4 | utf-8 | utf-8 | 通過 |
| 5 | cp932 | utf-8-sig (BOM付) | **ブロック** (utf-8 と検出) |
| 6 | cp932 | euc_jp | 検出不能(None) → 通過してしまう → 要対応 |
| 7 | cp932 | iso-2022-jp | cp932 誤検出 → 通過してしまう → 要対応 |
| 8 | ASCII のみ | ASCII のみ | 通過 (両方 cp932 判定) |
| 9 | (新規ファイル) | utf-8 | 通過 (HEAD なし) |
| 10 | denylist 違反 | - | **ブロック** |

### テスト6,7の対応方針

cp932 でも utf-8 でもデコードできないファイルは「不明なエンコーディング」としてブロックする。

**`pre_commit_encoding.py` への追加ロジック:**
- ステージされたファイルの `detect_encoding()` が `None` を返した場合、違反として報告・ブロック
- HEAD が存在しない新規ファイルでも、`None` の場合はブロック

**`check_encoding.py` (PostToolUse フック) への同様の追加:**
- 現在のファイルの `detect_encoding()` が `None` の場合も警告を出力

### テスト手順

1. テスト用 cp932 ファイルを作成 → commit で HEAD に登録
2. 各エンコーディングに書き換え → stage → commit 試行 → 結果確認
3. テストコミットを `git reset` で巻き戻し
4. 全テスト完了後クリーンアップ
