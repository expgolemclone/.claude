# Fix: ctrl+t ctrl+t で pwsh を新しいウィンドウで開く

## Context
`ctrl+t ctrl+t` に `workbench.action.terminal.openNativeConsole` を再割り当てする。
前回 conhost が開いていたのは Windows の既定ターミナルアプリ設定が原因。
VS Code 側のキーバインド復活 + Windows 側のレジストリ変更で解決する。

## 修正1: keybindings.json

**ファイル:** `C:\Users\0000250059\AppData\Roaming\Code\User\keybindings.json`

`ctrl+shift+alt+\`` の無効化エントリの直前に以下を追加:
```json
{
    "key": "ctrl+t ctrl+t",
    "command": "workbench.action.terminal.openNativeConsole",
    "when": "terminalHasBeenCreated || terminalProcessSupported"
},
```

## 修正2: Windows の既定ターミナルを Windows Terminal に変更

レジストリ `HKCU\Console\%%Startup` の以下の値を設定:
- `DelegationConsole` = `{2EACA947-7F5F-4CFA-BA87-8F7FBEEFBE69}` (Windows Terminal)
- `DelegationTerminal` = `{E12CFF52-A866-4C77-9A90-F570A7AA2C6B}` (Windows Terminal)

コマンド:
```
reg add "HKCU\Console\%%Startup" /v DelegationConsole /t REG_SZ /d "{2EACA947-7F5F-4CFA-BA87-8F7FBEEFBE69}" /f
reg add "HKCU\Console\%%Startup" /v DelegationTerminal /t REG_SZ /d "{E12CFF52-A866-4C77-9A90-F570A7AA2C6B}" /f
```

## 検証
1. VS Code を Reload Window
2. `ctrl+t ctrl+t` で Windows Terminal (pwsh) がワークスペースのパスで開くことを確認
3. conhost が出ないことを確認
