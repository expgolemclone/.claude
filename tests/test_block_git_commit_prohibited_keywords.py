"""Tests for block-git-commit-prohibited-keywords.py hook."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR
from tests.conftest import run_hook_process

HOOK = str(HOOKS_DIR / "block-git-commit-prohibited-keywords.py")


def run_hook(command: str) -> dict | None:
    return run_hook_process(HOOK, {"tool_input": {"command": command}})


# ---------------------------------------------------------------------------
# Should block
# ---------------------------------------------------------------------------

class TestBlock:
    def test_m_with_co_authored_by(self):
        result = run_hook('git commit -m "feat: add feature\n\nCo-Authored-By: Someone"')
        assert result["decision"] == "block"

    def test_m_with_claude(self):
        result = run_hook('git commit -m "fix: claude integration"')
        assert result["decision"] == "block"

    def test_m_with_anthropic_uppercase(self):
        result = run_hook('git commit -m "docs: update Anthropic SDK usage"')
        assert result["decision"] == "block"

    def test_heredoc_with_authored_in_body(self):
        cmd = '''git commit -m "$(cat <<'EOF'
feat: add new feature

Co-Authored-By: User <user@example.com>
EOF
)"'''
        result = run_hook(cmd)
        assert result["decision"] == "block"

    def test_heredoc_with_claude_in_body(self):
        cmd = '''git commit -m "$(cat <<'EOF'
feat: add feature

Generated with Claude Code
EOF
)"'''
        result = run_hook(cmd)
        assert result["decision"] == "block"

    def test_heredoc_with_anthropic_in_body(self):
        cmd = '''git commit -m "$(cat <<'EOF'
chore: update deps

noreply@anthropic.com
EOF
)"'''
        result = run_hook(cmd)
        assert result["decision"] == "block"

    def test_case_insensitive_claude(self):
        result = run_hook('git commit -m "CLAUDE generated this"')
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Should allow
# ---------------------------------------------------------------------------

class TestAllow:
    def test_normal_commit(self):
        assert run_hook('git commit -m "fix: resolve null pointer bug"') is None

    def test_not_a_git_commit(self):
        assert run_hook('echo "authored by claude at anthropic"') is None

    def test_git_add(self):
        assert run_hook("git add -A") is None

    def test_heredoc_without_keywords(self):
        cmd = '''git commit -m "$(cat <<'EOF'
feat: add login page

Added user authentication flow.
EOF
)"'''
        assert run_hook(cmd) is None

    def test_keyword_in_cd_path_not_message(self):
        cmd = 'cd "C:/Users/user/.claude" && git commit -m "fix: normal commit"'
        assert run_hook(cmd) is None

    def test_keyword_in_cd_path_with_heredoc(self):
        cmd = '''cd "/home/user/.claude" && git commit -m "$(cat <<'EOF'
feat: add hook registration

Added missing hooks to setup.py.
EOF
)"'''
        assert run_hook(cmd) is None
