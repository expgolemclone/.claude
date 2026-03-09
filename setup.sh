#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$SCRIPT_DIR/settings.json"

# Backup existing settings.json
if [[ -f "$TARGET" ]]; then
  cp "$TARGET" "$TARGET.bak"
  echo "Backed up: $TARGET -> $TARGET.bak"
fi

case "$(uname -s)" in
  Linux*)
    CLAUDE_HOME="$HOME/.claude"
    cat > "$TARGET" <<EOF
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  },
  "skipDangerousModePermissionPrompt": true,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          { "type": "command", "command": "python3 ${CLAUDE_HOME}/hooks/inject-rules.py" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 ${CLAUDE_HOME}/hooks/block-git-force-add.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_HOME}/hooks/post-edit-nixconfig.sh", "timeout": 5 }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_HOME}/hooks/post-bash-nixrebuild.sh", "timeout": 5 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "${CLAUDE_HOME}/hooks/stop-git-check.sh", "timeout": 15 }
        ]
      }
    ]
  }
}
EOF
    ;;
  MINGW*|MSYS*|CYGWIN*)
    CLAUDE_HOME="$(cygpath -m "$USERPROFILE")/.claude"
    # Backslash version for PowerShell paths
    CLAUDE_HOME_BS="$(cygpath -w "$USERPROFILE")\\.claude"
    cat > "$TARGET" <<EOF
{
  "permissions": {
    "deny": ["Task", "Agent"],
    "defaultMode": "bypassPermissions"
  },
  "skipDangerousModePermissionPrompt": true,
  "effortLevel": "high",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          { "type": "command", "command": "node \"${CLAUDE_HOME}/hooks/inject-rules.js\"" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "node \"${CLAUDE_HOME}/hooks/wsl-proxy.js\" pre" },
          { "type": "command", "command": "node \"${CLAUDE_HOME}/hooks/block-git-force-add.js\"" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "node \"${CLAUDE_HOME}/hooks/wsl-proxy.js\" post" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "pwsh -NoProfile -ExecutionPolicy Bypass -File \"${CLAUDE_HOME_BS}\\scripts\\notify-complete.ps1\"" }
        ]
      }
    ]
  }
}
EOF
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac

echo "Generated: $TARGET"
