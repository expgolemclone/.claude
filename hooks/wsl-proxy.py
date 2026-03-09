#!/usr/bin/env python3
"""PreToolUse/PostToolUse hook: manage WSL proxy for nixos-rebuild commands."""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time

PROXY_PORT = 8888
PID_FILE = os.path.join(tempfile.gettempdir(), "claude-wsl-proxy.pid")


def should_activate(command: str) -> bool:
    trimmed = command.strip()
    if not trimmed:
        return False
    if re.match(r"^wsl\s", trimmed, re.IGNORECASE) and "nixos-rebuild" in trimmed:
        return True
    if re.search(r"(?:^|[;&|]\s*)sudo\s+nixos-rebuild", trimmed):
        return True
    return False


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, timeout_ms: int = 3000) -> bool:
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        if is_port_in_use(port):
            return True
        time.sleep(0.2)
    return False


def output_feedback() -> None:
    msg = "\n".join(
        [
            "WSL proxy started on port 8888.",
            "nixos-rebuild command must include proxy env vars.",
            "Get the gateway IP inside WSL with: ip route show default | awk '{print $3}'",
            "Then pass: http_proxy=http://<GATEWAY_IP>:8888 https_proxy=http://<GATEWAY_IP>:8888",
            "Example: wsl -d NixOS -- bash -c 'export GW=$(ip route show default | awk \\'{print $3}\\'); sudo http_proxy=http://$GW:8888 https_proxy=http://$GW:8888 nixos-rebuild switch'",
        ]
    )
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}},
        sys.stdout,
    )


def handle_pre() -> None:
    if is_port_in_use(PROXY_PORT):
        output_feedback()
        return

    try:
        child = subprocess.Popen(
            ["proxy", "--hostname", "0.0.0.0", "--port", str(PROXY_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with open(PID_FILE, "w") as f:
            f.write(str(child.pid))
        wait_for_port(PROXY_PORT)
    except FileNotFoundError:
        pass

    output_feedback()


def handle_post() -> None:
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    try:
        os.unlink(PID_FILE)
    except OSError:
        pass


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")

    if not should_activate(command):
        return

    try:
        if mode == "pre":
            handle_pre()
        elif mode == "post":
            handle_post()
    except Exception as e:
        print(f"wsl-proxy hook error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
