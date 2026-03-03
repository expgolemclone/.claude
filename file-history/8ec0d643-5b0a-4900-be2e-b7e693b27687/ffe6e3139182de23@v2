# .hooks 総合テスト計画

## Context

`.hooks/` に pre-commit フック（encoding 変換 + denylist チェック）を整備した。
本番適用前に、リポジトリ全体に対してフックが正しく動作するかを総合テストする。

`context.md` の指示:
1. `.docs/`, `.hooks/`, `.vscode/`, `.gitignore` 以外を `origin/main` で上書き
2. commit して hooks を走らせ、encoding 変換と denylist 検出を検証

## Step 1: pre-commit スクリプトで denylist チェックを有効化

**ファイル:** `.hooks/pre-commit` (50-51行目)

コメントアウトを解除:
```bash
# 現状 (無効)
# echo "=== pre-commit: denylist check ==="
# python "$HOOKS_DIR/pre_commit_denylist.py"

# 変更後 (有効)
echo "=== pre-commit: denylist check ==="
python "$HOOKS_DIR/pre_commit_denylist.py"
```

## Step 2: pre_commit_denylist.py を ASCII 化

`pre_commit_encoding.py` と同様に、日本語コメントを英語に書き換える。
現状 `# coding: cp932` 付きで CP932 変換済みだが、Python のソースとして
ASCII only にすることで `.hooks/` 除外ルール不要・エンコーディング問題を回避する。

**ファイル:** `.hooks/pre_commit_denylist.py`

## Step 3: 保持対象以外のファイルを origin/main で上書き

```bash
git checkout origin/main -- ':!.docs' ':!.hooks' ':!.vscode' ':!.gitignore' ':!context.md'
```

これにより feat/NextGenRefact での変更（netsrc/, Build/, include/, src/ 等の
数百ファイル）が main と同じ状態にリセットされる。
`.docs/`, `.hooks/`, `.vscode/`, `.gitignore` は現在の状態を維持。

## Step 4: 全変更をステージしてコミット（総合テスト実行）

```bash
git add -A
git commit -m "test: run .hooks comprehensive test against full repository"
```

pre-commit フックが自動実行され、以下が検証される:
1. **encoding チェック**: 全追跡ファイルが CP932+CRLF に変換可能か
2. **denylist チェック**: .denylist パターン（strtok, gmtime 等）の検出

## Step 5: 結果確認

- encoding エラー → 該当ファイルの文字を修正 or 置換ルール追加
- denylist violation → レポート内容を確認（違反があっても期待通りならOK）
  - denylist は violation 発見時に exit 1 を返すので、コミットがブロックされる可能性あり
  - 初回テストでは violation レポートの確認が目的なので、必要に応じて一時的に対応を検討

## Verification

- pre-commit の出力で `converted (xxx -> cp932+crlf)` が表示される → encoding 変換成功
- `no denylist violations found.` or `DENYLIST: N violation(s)` が表示される → denylist 検出動作
- コミットが成功 or 想定通りのエラーで停止 → フック全体が正常動作
