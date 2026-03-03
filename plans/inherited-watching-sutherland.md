# Espanso → AutoHotkey v2 移行計画

## Context

espanso は Windows 環境で安定性に問題があり（ワーカークラッシュ、3プロセス必要、Rust製 watchdog が必要）、既に AHK v2 でキーバインド設定を運用中のため、テキスト展開機能も AHK に統合して espanso を完全に廃止する。

## ファイル構成

```
C:\Users\0000250059\Documents\AutoHotkey\
  test.ahk                       ← 既存（末尾に #Include 3行追加）
  expansions\
    base.ahk                     ← 新規: テキスト展開 (base.yml → 16トリガー)
    vscode-open.ahk              ← 新規: VSCode起動 (vscode-open.yml → 24トリガー)
    powershell-open.ahk           ← 新規: PowerShell起動 (powershell-open.yml → 20トリガー)
```

## 対象ファイル

| 操作 | ファイル |
|------|---------|
| 読取 | `espanso/match/base.yml` |
| 読取 | `espanso/match/vscode-open.yml` |
| 読取 | `espanso/match/powershell-open.yml` |
| 読取 | `espanso/config/default.yml` |
| 編集 | `C:\Users\0000250059\Documents\AutoHotkey\test.ahk` (末尾に3行追加) |
| 新規 | `C:\Users\0000250059\Documents\AutoHotkey\expansions\base.ahk` |
| 新規 | `C:\Users\0000250059\Documents\AutoHotkey\expansions\vscode-open.ahk` (23トリガー、`:esp` 削除) |
| 新規 | `C:\Users\0000250059\Documents\AutoHotkey\expansions\powershell-open.ahk` (19トリガー、`:sesp` 削除) |

## Step 1: `expansions\base.ahk` 作成

### ヘルパー関数

```ahk
PasteText(text, threshold := 100) {
    if StrLen(text) <= threshold {
        SendInput(text)
        return
    }
    saved := ClipboardAll()
    A_Clipboard := text
    if !ClipWait(2) {
        A_Clipboard := saved
        return
    }
    Sleep(300)          ; espanso pre_paste_delay 相当
    SendInput("^v")
    Sleep(400)          ; espanso restore_clipboard_delay 相当
    A_Clipboard := saved
}
```

### トリガー一覧 (16個)

| トリガー | 方式 | 備考 |
|---------|------|------|
| `:today` | `SendInput(FormatTime(, "yyyy-MM-dd"))` | |
| `:time` | `SendInput(FormatTime(, "HH:mm:ss"))` | |
| `:date` | `SendInput(FormatTime(, "MM/dd/yyyy"))` | |
| `:net` | `PasteText(...)` | 日本語金融計算式 |
| `:purenet` | `PasteText(...)` | 同上 |
| `:p` | `PasteText(...)` | AIプロンプトテンプレ (continuation section) |
| `:mail` | `PasteText(...)` | メール署名 (continuation section) |
| `:aq` | `PasteText(...)` | AquaVoice markdown修正テンプレ |
| `:da` | `PasteText(...)` | 日報 markdown修正テンプレ |
| `:fold` | `A_Clipboard` → `<details>` で囲む → `PasteText` | クリップボード使用 |
| `:mdscr` | GUI ListBox で言語選択 → ` ```lang\n{clipboard}\n``` ` | クリップボード+選択GUI |
| `:fix` | インライン `::fix-plan-muni-centroid` | 短いので直接置換 |
| `:gitremote` | `PasteText('git fetch --prune && ...')` | |
| `:gitlocal` | `PasteText('git push --force-with-lease ...')` | |
| `:c` | `SendInput('claude ""')` + `SendInput("{Left}")` | カーソル位置制御 |

### Hotstring 設定

- グローバル `#Hotstring *` (終了キー不要、espanso同様に即時発火)
- トリガー間のプレフィックス衝突なし（確認済み）

## Step 2: `expansions\vscode-open.ahk` 作成

### ヘルパー関数

```ahk
OpenInVSCode(path) {
    Run('"' EnvGet("LOCALAPPDATA") '\Programs\Microsoft VS Code\bin\code.cmd" "' path '"',, "Hide")
}
```

### トリガー一覧 (24個)

| トリガー | パス |
|---------|------|
| `:des` | `A_Desktop` |
| `:memo` | `A_Desktop "\memo"` |
| `:too` | `A_Desktop "\tool"` |
| `:sto` | `A_Desktop "\stock"` |
| `:land` | `A_Desktop "\stock\property\land_value_research"` |
| `:loc` | `A_Desktop "\local"` |
| `:play` | `A_Desktop "\local\playwright"` |
| `:refm` | `A_Desktop "\refactoring"` |
| `:refu` | `A_Desktop "\refactoring\ops5k_x64_utf-8_safefunc"` |
| `:refset` | `A_Desktop "\refactoring\OpsSetupForWin10_x64"` |
| `:res` | `A_Desktop "\restart"` |
| `:d\\` | `"D:\"` |
| `:dref` | `"D:\refactoring"` |
| `:mei` | `"D:\meisvy_line"` |
| `:tool` | `"E:\work\18.セットアップ(M5A Win10x64)\tool"` |
| `:scr` | `"E:\archive\screenshot"` |
| ~~`:esp`~~ | **削除** (espanso 廃止のため) |
| `:.codex` | `EnvGet("USERPROFILE") "\.codex"` |
| `:.claude` | `EnvGet("USERPROFILE") "\.claude"` |
| `:ahk` | `"C:\Users\0000250059\Documents\AutoHotkey\test.ahk"` (ファイル) |
| `:stav` | Startup フォルダパス |
| `:stae` | テキスト出力 `shell:startup\n` (VSCode起動ではない) |
| `:rep` | 動的パス: `FormatTime` で年月日を算出 → daily_repport パス |

### `:rep` の特殊処理

```ahk
:*::rep:: {
    y := FormatTime(, "yyyy")
    m := FormatTime(, "M")           ; 先頭ゼロなし (PowerShell .Month と同じ)
    d := FormatTime(, "yyyy-MM-dd")
    path := "C:\MEIDEN\Box\DA\システム管理課\K-教育訓練\新入社員教育など\20250804_教育資料（藤田充人）\daily_repport\" y "\" m "\" d ".md"
    OpenInVSCode(path)
}
```

## Step 3: `expansions\powershell-open.ahk` 作成

### ヘルパー関数

```ahk
OpenPowerShell(path) {
    Run("powershell.exe", path)
}
```

### トリガー一覧 (20個)

VSCode版と同一ディレクトリ、トリガーに `s` プレフィックス:
`:sdes`, `:smemo`, `:stoo`, `:ssto`, `:sland`, `:sloc`, `:splay`, `:srefm`, `:srefu`, `:srefset`, `:sres`, `:sd\\`, `:sdref`, `:smei`, `:stool`, `:sscr`, `:s.codex`, `:s.claude`, `:sahk`

> `:sesp` は削除（espanso 廃止のため）

特殊ケース:
- `:sahk` → `Run("C:\Users\0000250059\Documents\AutoHotkey\test.ahk")` (AHKスクリプト実行)
- `:sstav`, `:sstae` → Startup フォルダで PowerShell 起動（両方同じ動作）

## Step 4: `test.ahk` 末尾に追加

```ahk
; ==========================================
; テキスト展開 (espanso から移行)
; ==========================================
#Include "expansions\base.ahk"
#Include "expansions\vscode-open.ahk"
#Include "expansions\powershell-open.ahk"
```

## Watchdog について

**移行しない。** AHK は単一プロセスで安定しており、espanso のような3プロセス構成でのクラッシュ問題がない。Startup フォルダにショートカットを置くだけで十分。

## 検証手順

1. `test.ahk` をリロード (トレイアイコン → Reload)
2. メモ帳で各トリガーをテスト:
   - `:today` → `2026-02-26` が出力されるか
   - `:mail` → 複数行の署名が正しく貼り付くか
   - `:fold` → クリップボード内容が `<details>` タグで囲まれるか
   - `:mdscr` → GUI が表示され、選択した言語でコードブロックが出力されるか
   - `:c` → `claude ""` でカーソルが引用符の間にあるか
3. `:des` → VSCode が Desktop を開くか
4. `:sdes` → PowerShell が Desktop で開くか
5. `:rep` → 今日の日付の日報パスで VSCode が開くか
6. 全58トリガーを一通りテスト (16 + 23 + 19 = 58、`:esp` と `:sesp` 削除)
