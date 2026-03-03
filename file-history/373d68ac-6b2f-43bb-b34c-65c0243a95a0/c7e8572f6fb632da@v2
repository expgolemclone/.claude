# settings.json に Stop hook を追加

## Context
タスク完了時に通知スクリプト (`notify-complete.ps1`) を実行する Stop hook を追加する。

## 変更対象
- `C:\Users\0000250059\.claude\settings.json`

## 変更内容
`hooks` オブジェクトに以下の `Stop` キーを追加:

```json
"Stop": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "pwsh -NoProfile -ExecutionPolicy Bypass -File \"C:\\Users\\0000250059\\.claude\\scripts\\notify-complete.ps1\""
      }
    ]
  }
]
```

既存の `PreToolUse` はそのまま維持。

## 検証
- `settings.json` が valid JSON であること
- 既存の hooks が壊れていないこと
