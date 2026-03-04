#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [[ "$FILE_PATH" != *.ahk ]]; then
  exit 0
fi

AHK_DIR="C:/Users/0000250059/Documents/AutoHotkey"
AHK_EXE="$AHK_DIR/.tools/AutoHotkey-v2/AutoHotkey64.exe"

taskkill //F //IM AutoHotkey64.exe > /dev/null 2>&1

for launcher in "$AHK_DIR"/*-launcher.ahk; do
  start "$AHK_EXE" "$launcher"
done
