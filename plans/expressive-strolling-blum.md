# Plan: エンコーディング破損ファイル27件の修復 + ビルドエラー修正

## Context

Pythonスクリプトで strtok/getenv/strerror/gmtime/localtime の置換を行った際、一部のスクリプトが cp932 ファイルを UTF-8 (U+FFFD replacement character 0xEFBFBD) に変換して書き戻してしまった。27ファイルが破損し、ビルドエラー (aoalm.c C2660/C2065, aosysi.c C2065, hoe_rcv_ssl.c C2001 等) が発生。

## Step 1: 全27ファイルを git 原本から復元

```bash
git checkout HEAD -- src/NX_MW/dfstat/main.c src/NX_MW/libdl/liberrlog.c src/NX_MW/nxstat/main.c src/NX_MW/opsnexus/deliv.c src/NX_MW/opsnexus/init.c src/NX_MW/opsnexus/liberrlog.c src/ens/Dll/ledocm_dll/dl_SubProc.c src/ens/Dll/lelogf_dll/Lelogf.c src/gen/Genset/Genset100.c src/gen/Genset/Genset600.c src/his/dohstg/hstg120.c src/his/domdcl/mdcl160.c src/kcrt/gosav/gosavlib.c src/lib/vc/fsectoun.c src/lib/vc/fsectoun24.c src/lnk/jorepfl/jorepfl.c src/mail/hoemls/hoe_rcv_ssl.c src/msg/cotalk/f_tlk.c src/sys/aoalm/aoalm.c src/sys/aosysi/aosysi.c src/tool/ErrorLog/ErrorLogView.cpp src/tool/NTP/NTPcheck/NTPcheck.c src/tool/NTP/NTPclient/NTPclient.c src/tool/NTP/NTPclient2/NTPclient2.c src/tool/NTP/NTPserver/NTPserver.c src/tool/NTP/NTPtest/NTPtest.c src/tool/jotesttool/jotesttool.c
```

## Step 2: `fix_corrupted_27.py` で再変換

1つの Python スクリプトで全27ファイルを処理。**エンコーディング保全**: `open(rb)` → `decode('cp932')` → 置換 → `encode('cp932')` → `open(wb)`

### 各ファイルに必要な置換マッピング

| # | ファイル | strtok | getenv | strerror | gmtime | localtime | comment-only |
|---|---------|--------|--------|----------|--------|-----------|-------------|
| 1 | NX_MW/dfstat/main.c | | | | 1 | | localtime(comment) |
| 2 | NX_MW/libdl/liberrlog.c | | | | | | localtime(comment) |
| 3 | NX_MW/nxstat/main.c | | | | 1 | | localtime(comment) |
| 4 | NX_MW/opsnexus/deliv.c | | | 2 | | | |
| 5 | NX_MW/opsnexus/init.c | 21 | | 3+1comment | | | |
| 6 | NX_MW/opsnexus/liberrlog.c | | | | | | localtime(comment) |
| 7 | ens/Dll/ledocm_dll/dl_SubProc.c | | 1 | | | | |
| 8 | ens/Dll/lelogf_dll/Lelogf.c | | 2active+2comment | | | | |
| 9 | gen/Genset/Genset100.c | | 2(conditional) | | | | |
| 10 | gen/Genset/Genset600.c | | 2 | | | | |
| 11 | his/dohstg/hstg120.c | 2 | | | | | |
| 12 | his/domdcl/mdcl160.c | 2 | | | | | |
| 13 | kcrt/gosav/gosavlib.c | | | | | 1 | |
| 14 | lib/vc/fsectoun.c | | | | 1 | | |
| 15 | lib/vc/fsectoun24.c | | | | 1 | | |
| 16 | lnk/jorepfl/jorepfl.c | 3 | 1 | | | | |
| 17 | mail/hoemls/hoe_rcv_ssl.c | 8 | | | | | |
| 18 | msg/cotalk/f_tlk.c | | | | | | localtime(comment) |
| 19 | sys/aoalm/aoalm.c | 4 | 1 | | | | |
| 20 | sys/aosysi/aosysi.c | 146 | | | | | gmtime(comment) |
| 21 | tool/ErrorLog/ErrorLogView.cpp | | | | | 1 | |
| 22 | tool/NTP/NTPcheck/NTPcheck.c | | | | 1 | | |
| 23 | tool/NTP/NTPclient/NTPclient.c | | | | 1 | | |
| 24 | tool/NTP/NTPclient2/NTPclient2.c | | | | 1 | | |
| 25 | tool/NTP/NTPserver/NTPserver.c | | | | 1 | | |
| 26 | tool/NTP/NTPtest/NTPtest.c | | | | 1 | | |
| 27 | tool/jotesttool/jotesttool.c | | | | 18 | | |

### 置換パターン詳細

**Pattern A: gmtime → gmtime_s**
```c
// Before:
struct tm *VAR;
VAR = gmtime(arg);
x = VAR->tm_year;

// After:
struct tm VAR_buf;           // *削除, _buf追加
gmtime_s(&VAR_buf, arg);    // 代入削除, gmtime_sに変更
x = VAR_buf.tm_year;        // -> を . に変更
```
変数名マッピング:
- dfstat/main.c, nxstat/main.c: `tm_p` → `tm_p` (元コードにコメントアウトで `struct tm tm_p` が既にある)
- fsectoun.c, fsectoun24.c, NTP5ファイル: `tmt` → `tmt_buf`
- jotesttool.c: `tim_t` → `tim_t_buf`

**Pattern B: localtime → localtime_s**
```c
// Before:
struct tm *VAR;
VAR = localtime(&arg);
x = VAR->member;

// After:
struct tm VAR_buf;
localtime_s(&VAR_buf, &arg);
x = VAR_buf.member;
```
変数名マッピング:
- gosavlib.c: `date` → `date_buf`
- ErrorLogView.cpp: `pTm` → `pTm_buf` (C++形式: `tm* pTm` → `tm pTm_buf`)

**Pattern C: strerror → strerror_s** (init.c, deliv.c)
```c
// Before:
sprintf(buf, "func(): %s", strerror(errno));

// After:
strerror_s(strerr_buf, sizeof(strerr_buf), errno);
sprintf(buf, "func(): %s", strerr_buf);
// 宣言追加: char strerr_buf[256];
```

**Pattern D: getenv → getenv_s**
```c
// Before:
var = getenv("NAME");

// After:
getenv_s(&env_len, env_buf, sizeof(env_buf), "NAME");
// var参照 → env_buf, NULLチェック → env_len==0 チェック
// 宣言追加: size_t env_len; char env_buf[256];
```
特殊ケース:
- Genset100.c: 条件式内代入 `if ((chk_c = getenv("X")) != NULL)` 形式
- Lelogf.c: `strcpy_s(dst, sz, getenv("X"))` → 2段階に分離
- dl_SubProc.c: `env_cp = getenv("X")` → getenv_s + env_cp→env_buf

**Pattern E: strtok → strtok_s** (既存 `.docs/refact_1/scripts/replace_strtok.py` と同ロジック)
```c
// Before:
p = strtok(str, delim);
p = strtok(NULL, delim);

// After:
char *strtok_ctx = NULL;    // 関数先頭に宣言追加
p = strtok_s(str, delim, &strtok_ctx);
p = strtok_s(NULL, delim, &strtok_ctx);
```

**Pattern F: コメント内の関数名置換**
- `localtime(` → `localtime_s(` (4ファイル: dfstat, nxstat, libdl/liberrlog, opsnexus/liberrlog, f_tlk)
- `gmtime(` → `gmtime_s(` (aosysi.c コメント)
- `strerror(` → `strerror_s(` (init.c コメント)

### スクリプト構造

```python
# fix_corrupted_27.py
# 1. FILE_CONFIG辞書: ファイルパス → {patterns: [A,B,C,D,E,F], gmtime_var: {...}, ...}
# 2. 各パターンの変換関数 (既存スクリプトのロジック再利用)
# 3. メインループ: ファイルごとに rb読み→cp932 decode→変換→cp932 encode→wb書き
```

## Step 3: 検証

```bash
python .hooks/pre_commit_denylist.py   # 0 violations 確認
```

さらにユーザーに `build_errors.txt` 再ビルドを依頼。

## 55ファイル (正常変更済み)

変更不要。そのまま。
