#!/usr/bin/env python3
"""Tests for block-git-commit-keywords.py hook."""

import json
import subprocess
import sys

HOOK = "/home/exp/.claude/hooks/block-git-commit-keywords.py"


def run_hook(command: str) -> dict | None:
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test(name: str, command: str, *, should_block: bool) -> bool:
    result = run_hook(command)
    blocked = result is not None and result.get("decision") == "block"
    ok = blocked == should_block
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"         expected={'block' if should_block else 'allow'}, got={'block' if blocked else 'allow'}")
        if result:
            print(f"         reason: {result.get('reason')}")
    return ok


def main() -> None:
    results: list[bool] = []

    print("--- should block ---")
    results.append(test(
        "-m with Co-Authored-By",
        'git commit -m "feat: add feature\n\nCo-Authored-By: Someone"',
        should_block=True,
    ))
    results.append(test(
        "-m with claude",
        'git commit -m "fix: claude integration"',
        should_block=True,
    ))
    results.append(test(
        "-m with Anthropic (uppercase)",
        'git commit -m "docs: update Anthropic SDK usage"',
        should_block=True,
    ))
    results.append(test(
        "HEREDOC with authored in body",
        '''git commit -m "$(cat <<'EOF'
feat: add new feature

Co-Authored-By: User <user@example.com>
EOF
)"''',
        should_block=True,
    ))
    results.append(test(
        "HEREDOC with claude in body",
        '''git commit -m "$(cat <<'EOF'
feat: add feature

Generated with Claude Code
EOF
)"''',
        should_block=True,
    ))
    results.append(test(
        "HEREDOC with anthropic in body",
        '''git commit -m "$(cat <<'EOF'
chore: update deps

noreply@anthropic.com
EOF
)"''',
        should_block=True,
    ))
    results.append(test(
        "case insensitive: CLAUDE",
        'git commit -m "CLAUDE generated this"',
        should_block=True,
    ))

    print("\n--- should allow ---")
    results.append(test(
        "normal commit",
        'git commit -m "fix: resolve null pointer bug"',
        should_block=False,
    ))
    results.append(test(
        "not a git commit command",
        'echo "authored by claude at anthropic"',
        should_block=False,
    ))
    results.append(test(
        "git add (not commit)",
        'git add -A',
        should_block=False,
    ))
    results.append(test(
        "HEREDOC without keywords",
        '''git commit -m "$(cat <<'EOF'
feat: add login page

Added user authentication flow.
EOF
)"''',
        should_block=False,
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 30}")
    print(f"Results: {passed}/{total} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
