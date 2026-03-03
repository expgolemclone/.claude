# ランチャースクリプトの管理者権限降格

## Context
`vscode-open-launcher.ahk` / `powershell-open-launcher.ahk` は管理者コンテキストから起動すると管理者権限を継承してしまう。shell:startup からの起動は問題ないが、手動再起動時に管理者権限になる。

## 方針
両ランチャーに `A_IsAdmin` チェックを追加し、管理者権限で実行された場合は `runas /trustlevel:0x20000` で通常権限として自身を再起動する。

`runas /trustlevel:0x20000` は Windows 標準の権限降格コマンド。

## 変更対象
- `vscode-open-launcher.ahk`
- `powershell-open-launcher.ahk`

## 変更内容
各ファイルの先頭に以下を追加:

```ahk
if A_IsAdmin {
    Run("runas /trustlevel:0x20000 " '"' A_AhkPath '" "' A_ScriptFullPath '"')
    ExitApp
}
```

## 検証
1. 管理者権限ターミナルから両スクリプトを起動
2. タスクマネージャーで該当プロセスが「昇格」されていないことを確認
