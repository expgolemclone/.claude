#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): inject rebuild instruction when nix-config files are edited

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" == /home/exp/nix-config/* ]]; then
  jq -n '{
    "decision": "block",
    "reason": "nix-config file was modified. Run: sudo nixos-rebuild switch --flake ~/nix-config#nixos"
  }'
  exit 0
fi

exit 0
