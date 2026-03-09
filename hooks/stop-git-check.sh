#!/usr/bin/env bash
# Stop hook: block if there are uncommitted or unpushed changes in a git repo

INPUT=$(cat)

# Prevent infinite loop when stop hook is already active
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
  exit 0
fi

CWD=$(echo "$INPUT" | jq -r '.cwd')

# Check if we're in a git repository
if ! git -C "$CWD" rev-parse --is-inside-work-tree &>/dev/null; then
  exit 0
fi

ISSUES=""

# Check for uncommitted changes (staged, unstaged, untracked)
UNCOMMITTED=$(git -C "$CWD" status --porcelain 2>/dev/null)
if [ -n "$UNCOMMITTED" ]; then
  ISSUES="${ISSUES}Uncommitted changes detected:\n${UNCOMMITTED}\n\n"
fi

# Check for unpushed commits
UPSTREAM=$(git -C "$CWD" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)
if [ -n "$UPSTREAM" ]; then
  UNPUSHED=$(git -C "$CWD" log '@{upstream}..HEAD' --oneline 2>/dev/null)
  if [ -n "$UNPUSHED" ]; then
    ISSUES="${ISSUES}Unpushed commits detected:\n${UNPUSHED}\n\n"
  fi
fi

if [ -n "$ISSUES" ]; then
  jq -n --arg reason "$(echo -e "$ISSUES")Commit and push all changes before finishing." \
    '{"decision": "block", "reason": $reason}'
  exit 0
fi

exit 0
