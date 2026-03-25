"""Tests for block-git-commit-prohibited-keywords.py hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR

HOOK = str(HOOKS_DIR / "block-git-commit-prohibited-keywords.py")


def run_hook(command: str, cwd: str | None = None) -> dict | None:
    """Run the hook, optionally overriding the working directory."""
    payload = {"tool_input": {"command": command}}
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


@pytest.fixture()
def clean_repo(tmp_path: Path) -> Path:
    """Git repo with only clean commits."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("hello")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "feat: initial commit")
    return tmp_path


@pytest.fixture()
def tainted_repo(tmp_path: Path) -> Path:
    """Git repo with a commit containing a prohibited keyword."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("hello")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "feat: add claude integration")
    (tmp_path / "b.txt").write_text("world")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "fix: clean follow-up")
    return tmp_path


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

    @pytest.mark.parametrize("keyword", [
        "ai", "llm", "gemini", "openai", "foundation",
        "copilot", "gpt", "chatgpt", "bard",
        "codeium", "cursor", "tabnine", "cody", "devin",
        "agent", "assistant", "auth", "エージェント",
    ])
    def test_all_keywords_blocked(self, keyword):
        result = run_hook(f'git commit -m "feat: use {keyword} for generation"')
        assert result is not None and result["decision"] == "block", keyword


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

    @pytest.mark.parametrize("msg", [
        "fix: maintain backward compatibility",    # contains "ai" substring
        "feat: add wait logic for retries",        # contains "ai" substring
        "fix: certain edge cases",                 # contains "ai" substring
        "feat: update training data pipeline",     # contains "ai" substring
        "feat: add user authentication flow",      # contains "auth" substring
        "fix: authorization header parsing",       # contains "auth" substring
        "feat: reagent pattern for state mgmt",    # contains "agent" substring
    ])
    def test_word_boundary_no_false_positive(self, msg):
        assert run_hook(f'git commit -m "{msg}"') is None


# ---------------------------------------------------------------------------
# git push: should block when log contains keywords
# ---------------------------------------------------------------------------

class TestPushBlock:
    def test_push_blocks_when_log_has_keyword(self, tainted_repo):
        result = run_hook("git push", cwd=str(tainted_repo))
        assert result is not None
        assert result["decision"] == "block"

    def test_push_blocks_with_origin_main(self, tainted_repo):
        result = run_hook("git push origin main", cwd=str(tainted_repo))
        assert result is not None
        assert result["decision"] == "block"

    def test_push_reason_shows_offending_hash(self, tainted_repo):
        result = run_hook("git push", cwd=str(tainted_repo))
        assert "claude" in result["reason"].lower()


# ---------------------------------------------------------------------------
# git push: should allow when log is clean
# ---------------------------------------------------------------------------

class TestPushAllow:
    def test_push_allows_clean_repo(self, clean_repo):
        result = run_hook("git push", cwd=str(clean_repo))
        assert result is None

    def test_push_allows_clean_repo_with_remote(self, clean_repo):
        result = run_hook("git push origin main", cwd=str(clean_repo))
        assert result is None
