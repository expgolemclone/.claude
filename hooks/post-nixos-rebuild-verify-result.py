#!/usr/bin/env python3
"""PostToolUse hook (Bash): follow up after nixos-rebuild commands."""

import json
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if "nixos-rebuild" not in command:
        return

    tool_response = data.get("tool_response", "")

    if re.search(r"error|failed|failure|trace:", tool_response, re.IGNORECASE):
        json.dump(
            {
                "decision": "block",
                "reason": "nixos-rebuild failed. Fix the error and run rebuild again: sudo nixos-rebuild switch --flake ~/nix-config#nixos",
            },
            sys.stdout,
        )
    else:
        json.dump(
            {
                "decision": "block",
                "reason": "nixos-rebuild succeeded. Now check Hyprland logs for errors: journalctl --user -u hyprland-session.service -n 50 --no-pager || journalctl --user -b -g Hyprland --no-pager | tail -50",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
