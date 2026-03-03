# TODO.md 実装プラン: 拡張子別ルール自動注入hookの有効化

## Context

`~/.claude/TODO.md` に記載された「拡張子ごとのコーディングルールをhookで自動注入する仕組み」を完成させる。hookスクリプト (`inject-rules.sh`) とルールファイルの雛形は既に存在するが、**hookがsettings.jsonに未登録**かつ**ルールファイルが空**のため、仕組みが動作していない。

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `~/.claude/settings.json` | `hooks` ブロックを追加してPreToolUseに登録 |
| `~/.claude/hooks/inject-rules.sh` | PostToolUse → PreToolUse に変更 + `.tool_input.path` フォールバック追加 |
| `~/.claude/rules/py.md` | Python規約を記載 |
| `~/.claude/rules/rs.md` | Rust規約を記載 |
| `~/.claude/rules/ps1.md` | PowerShell規約を記載 |
| `~/.claude/rules/md.md` | Markdown規約を記載 |
| `~/.claude/rules/git.md` | Git規約を記載 |
| `~/.claude/rules/cs.md` | C#規約を新規作成（TODO.mdで言及あり） |
| `~/.claude/rules/c.md` | C規約を新規作成（TODO.mdで言及あり） |

## Step 1: settings.json にhookを登録

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  },
  "skipDangerousModePermissionPrompt": true,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$HOME/.claude/hooks/inject-rules.sh\""
          }
        ]
      }
    ]
  }
}
```

## Step 2: inject-rules.sh を修正

2箇所の変更:
- L4: `.tool_input.path` のフォールバック追加
- L23: `hookEventName` を `"PreToolUse"` に変更

```bash
#!/bin/bash
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")
EXT="${BASENAME##*.}"

if [[ -z "$EXT" || "$EXT" == "$BASENAME" ]]; then
  exit 0
fi

EXT=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')
RULES_FILE="$HOME/.claude/rules/${EXT}.md"

if [[ -s "$RULES_FILE" ]]; then
  RULES_CONTENT=$(cat "$RULES_FILE")
  jq -n --arg ctx "$RULES_CONTENT" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
```

**PreToolUseを選択した理由**: ルールをEditの**実行前**にコンテキスト注入することで、**現在の編集**に規約を反映できる。PostToolUseだと次回以降の編集にしか効かない。

## Step 3: ルールファイルを記載

各ファイルに簡潔な言語規約を記載する。TODO.mdの例で言及されている `cs.md`、`c.md` も新規作成する。内容は各言語の標準的なコーディング規約を簡潔にまとめたもの（各ファイル10行程度）。

## Step 4: 動作確認

```bash
# jqが使えることを確認
jq --version

# hookスクリプトの動作テスト
echo '{"tool_name":"Edit","tool_input":{"file_path":"test.py"}}' | bash ~/.claude/hooks/inject-rules.sh

# 期待: py.md の内容を含むJSON出力

# 拡張子なしファイルのテスト（何も出力されないこと）
echo '{"tool_name":"Edit","tool_input":{"file_path":"Makefile"}}' | bash ~/.claude/hooks/inject-rules.sh

# 期待: 出力なし（exit 0）
```

設定変更後、Claude Codeセッションの再起動が必要。
