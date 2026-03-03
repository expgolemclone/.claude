# Plan: aosysi.c ビルドエラー修正

## Context
前回の `strtok()` → `strtok_s()` 一括置換で、`aosysi.c` の `f_sys440` 関数内で `char *strtok_ctx = NULL;` が配列初期化子の途中に誤挿入された。
これにより C2062 等のビルドエラーが連鎖発生している。他37ファイルは問題なし。

## 原因
`static char token_c[][32] = { ... };` の途中にコメント行 `//   "P-NET回線種別"} ;` があり、スクリプトがそこを宣言部の終わりと誤認した。

## 修正内容 (aosysi.c のみ)

### 修正箇所: `src/sys/aosysi/aosysi.c`

**4308行目を削除** (配列初期化子内の誤挿入):
```
     char	*strtok_ctx = NULL;    ← この行を削除
```

**4323行目の後に挿入** (`Ada_TaskList_s` 配列の `};` の後、空行の後):
```c
  char	*strtok_ctx = NULL;
```

### スクリプト修正: `.docs/refact_1/scripts/replace_strtok.py`
`find_decl_insert_point` 関数で、未閉じのブレース `{` 内にいる場合は宣言部の終了と判定しないように修正。

## 検証
1. `python .hooks/pre_commit_denylist.py` → 違反ゼロ
2. `python .hooks/pre_commit_encoding.py` → 違反ゼロ
3. ビルド再実行でエラーがないことを確認
