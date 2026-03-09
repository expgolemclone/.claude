#!/usr/bin/env bash
# PostToolUse hook (Bash): follow up after nixos-rebuild commands

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only act on nixos-rebuild commands
if [[ "$COMMAND" != *"nixos-rebuild"* ]]; then
  exit 0
fi

TOOL_RESPONSE=$(echo "$INPUT" | jq -r '.tool_response // empty')

# Check for failure indicators
if echo "$TOOL_RESPONSE" | grep -qiE 'error|failed|failure|trace:'; then
  jq -n '{
    "decision": "block",
    "reason": "nixos-rebuild failed. Fix the error and run rebuild again: sudo nixos-rebuild switch --flake ~/nix-config#nixos"
  }'
  exit 0
fi

# Success: instruct to check Hyprland logs
jq -n '{
  "decision": "block",
  "reason": "nixos-rebuild succeeded. Now check Hyprland logs for errors: journalctl --user -u hyprland-session.service -n 50 --no-pager || journalctl --user -b -g Hyprland --no-pager | tail -50"
}'
exit 0
