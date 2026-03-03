# pre_commit_encoding.py — null byte バグ修正

## Context
前回の変更で `main()` 内に追加した `split("\0")` のうち、ソースコード中にリテラル null byte (`\x00`) が埋め込まれてしまっている。
offset 6572 の `split("\x00")` → `split("\0")` (バックスラッシュ+ゼロ) に修正する。

## 変更内容

### `D:\refactoring\ops5k_x64\.hooks\pre_commit_encoding.py`

バイト置換: offset 6572 付近の `\x22\x00\x22` (リテラル null) → `\x22\x5c\x30\x22` (`"\0"` as source)

## 検証
- `python .hooks/pre_commit_encoding.py` がエラーなく実行できること
- `git commit` 時に `git add` エラーが発生しないこと
