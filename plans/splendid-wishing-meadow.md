# 非スレッドセーフ関数の1関数ずつ置換 — キュー管理の仕組み

## Context

`unsafe_to_safe.csv`に10関数の置換ペアがあるが、全部を一度にClaudeに渡すとコンテキストが汚れ、output精度が下がる。手動で毎回ファイルを書き換えるのも面倒。

**解決策**: コードベースをスキャンして「次にやるべき1関数」を自動判定し、`current_target.csv`（1行だけ）と`.denylist`（1パターンだけ）を生成するPythonスクリプトを作る。

## 方式: 自動検出 + CSV順序

- `unsafe_to_safe.csv`を上から順に走査
- `src/`内でまだ違反が残っている最初の関数を「現在のターゲット」にする
- 状態ファイル不要（コードベース自体が進捗のソース）
- 中断しても再実行すれば同じ関数に戻る

## 変更ファイル一覧

| ファイル | 操作 |
|---------|------|
| `.docs/refact_1/scripts/advance_target.py` | **新規作成** |
| `CLAUDE.md` | **編集** |
| `.hooks/current_target.csv` | スクリプトが自動生成 |
| `.hooks/.denylist` | スクリプトが上書き |

## 1. `advance_target.py` 新規作成

**場所**: `.docs/refact_1/scripts/advance_target.py`

**動作**:
```
python .docs/refact_1/scripts/advance_target.py
```

1. `unsafe_to_safe.csv`を読み込む
2. 各関数について`src/`内の違反数をカウント（エンコーディング処理は`pre_commit_denylist.py`と同じ: cp932 → utf-8 → latin-1）
3. 進捗一覧を表示:
   ```
   === Unsafe Function Replacement Progress ===
     [x] asctime() -> asctime_s()   (DONE)
     [ ] strtok() -> strtok_s()     (346 remaining)
     ...
   >>> CURRENT TARGET: strtok() -> strtok_s()
       Violations: 346 in 38 file(s)
   ```
4. 最初の未完了関数を`.hooks/current_target.csv`に書き出し（ヘッダ+1行のみ）
5. `.hooks/.denylist`をその関数のパターン1つだけに上書き
6. 全完了時は「ALL DONE」と表示、`current_target.csv`を削除

**ポイント**:
- 既存の`pre_commit_denylist.py`はコード変更不要（`.denylist`を動的に読むため）
- `.hooks/check_diff_size.py`, `check_encoding.py`, `.claude/settings.json` も変更不要

## 2. `CLAUDE.md` 編集

主な変更点:
- `unsafe_to_safe.csv`への参照 → `current_target.csv`に変更
- 「1セッション1関数」のルールを明記
- DON'T DOに「current_target.csvに記載されていない関数の置き換え禁止」を追加
- DOに「まず`.hooks/current_target.csv`を読んで対象関数を確認する」を追加

## ワークフロー

```
# 1. セッション開始前にスクリプト実行
python .docs/refact_1/scripts/advance_target.py

# 2. Claude Code セッション開始
#    → CLAUDE.mdが current_target.csv を参照
#    → Claudeは1関数だけ見える

# 3. 作業完了・commit後、再度スクリプト実行
python .docs/refact_1/scripts/advance_target.py
#    → 完了していれば次の関数に自動進行
#    → 中断なら同じ関数に留まる
```

## エッジケース

- **中断**: 再実行で同じ関数に戻る（違反が残っているため）
- **違反0の関数**: 自動スキップ（asctime, rand, srand, tmpnamは現在0件）
- **全完了**: `current_target.csv`削除、`.denylist`空化

## 検証手順

1. `advance_target.py`を実行し、進捗一覧と`current_target.csv`の内容を確認
2. `.hooks/.denylist`が1パターンのみになっていることを確認
3. `python .hooks/pre_commit_denylist.py`が対象関数の違反のみ報告することを確認
4. Claude Codeセッションで`CLAUDE.md`が`current_target.csv`を参照していることを確認
