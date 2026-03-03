# PostToolUse フック: 拡張子別ルール自動注入

## Context

`.claude/rules/{ext}.md` に言語別ルールを配置済みだが、自動注入の仕組み（PostToolUse hook）が未構築。
Edit/Write 実行時に対象ファイルの拡張子を判定し、該当ルールを Claude のコンテキストに注入するフックを作成する。

## 重要な設計変更点

ユーザー提示のスクリプトでは `cat` で stdout に出力しているが、**PostToolUse フックでは `additionalContext` を含む JSON を出力しないとコンテキストに注入されない**。単なる stdout テキストは verbose モード以外では破棄される。

## 実装手順

### Step 1: `~/.claude/hooks/` ディレクトリ作成

```bash
mkdir -p ~/.claude/hooks
```

### Step 2: フックスクリプト作成

**ファイル:** `~/.claude/hooks/inject-rules.sh`

```bash
#!/bin/bash
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

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
      hookEventName: "PostToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
```

**ポイント:**
- ユーザーの if/elif チェーンではなく、拡張子から動的にファイルパスを構築 → 新言語追加時にスクリプト変更不要
- `-s` で空ファイルはスキップ（`py.md` 等の未記入ファイルは無視される）
- `jq -n --arg` で安全に JSON 構築（改行・特殊文字をエスケープ）
- 大文字拡張子も `tr` で正規化

### Step 3: 実行権限付与

```bash
chmod +x ~/.claude/hooks/inject-rules.sh
```

### Step 4: `settings.json` にフック登録

**ファイル:** `~/.claude/settings.json`

既存の `permissions` を維持しつつ `hooks` を追加:

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  },
  "hooks": {
    "PostToolUse": [
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

### Step 5: jq の存在確認

スクリプトは `jq` に依存。未インストールなら導入が必要。

### Step 6: 動作テスト

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/c/Users/test/diagram.mmd"}}' \
  | bash ~/.claude/hooks/inject-rules.sh
```

`mmd.md` の内容が `additionalContext` として JSON 出力されれば成功。

## 対象ファイル

| ファイル | 操作 |
|---|---|
| `~/.claude/hooks/inject-rules.sh` | 新規作成 |
| `~/.claude/settings.json` | 編集（hooks 追加） |

## 検証方法

1. 上記の手動テストコマンドで JSON 出力を確認
2. Claude Code セッションを再起動し、`.mmd` ファイルを Edit → Mermaid テーマルールが注入されることを確認
3. 拡張子なしファイル・未知の拡張子で空出力になることを確認
