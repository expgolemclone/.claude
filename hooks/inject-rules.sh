#!/bin/bash
INPUT=$(cat)

RULES_CONTENT=""

# Bash ツールで git コマンド実行時 → git.toml を注入
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if [[ -n "$COMMAND" && "$COMMAND" =~ ^[[:space:]]*(git[[:space:]]) ]]; then
  GIT_RULES="$HOME/.claude/rules/git.toml"
  if [[ -s "$GIT_RULES" ]]; then
    RULES_CONTENT=$(cat "$GIT_RULES")
  fi
  if [[ -n "$RULES_CONTENT" ]]; then
    jq -n --arg ctx "$RULES_CONTENT" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: $ctx
      }
    }'
  fi
  exit 0
fi

# Edit/Write ツール → 拡張子ベースのルール注入
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
RULES_FILE="$HOME/.claude/rules/${EXT}.toml"

RULES_CONTENT=""

if [[ -s "$RULES_FILE" ]]; then
  RULES_CONTENT=$(cat "$RULES_FILE")
fi

# .md 編集時は mmd.toml (Mermaid ルール) も追加注入
if [[ "$EXT" == "md" ]]; then
  MMD_FILE="$HOME/.claude/rules/mmd.toml"
  if [[ -s "$MMD_FILE" ]]; then
    RULES_CONTENT="${RULES_CONTENT}"$'\n\n'"$(cat "$MMD_FILE")"
  fi
fi

if [[ -n "$RULES_CONTENT" ]]; then
  jq -n --arg ctx "$RULES_CONTENT" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
