"""Tests for block-protected-nix-config.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("block-protected-nix-config")
check_edit = mod.check_edit
check_write = mod.check_write
main = mod.main

CONFIG = "hosts/nixos/configuration.nix"


def run_main(stdin_data: dict) -> dict | None:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            main()
        raw = out.getvalue()
        return json.loads(raw) if raw else None


def edit_input(file_path: str, old: str, new: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": old, "new_string": new},
    }


def write_input(file_path: str, content: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


# ---------------------------------------------------------------------------
# Edit — should block
# ---------------------------------------------------------------------------

class TestEditBlock:
    def test_1_sysusers_enable_change(self):
        result = run_main(edit_input(
            CONFIG,
            "  systemd.sysusers.enable = false;",
            "  systemd.sysusers.enable = true;",
        ))
        assert result["decision"] == "block"

    def test_2_initial_password_change(self):
        result = run_main(edit_input(
            CONFIG,
            '    initialPassword = "pa";',
            '    initialPassword = "newpass";',
        ))
        assert result["decision"] == "block"

    def test_3_mutable_users_deleted(self):
        result = run_main(edit_input(
            CONFIG,
            "  users.mutableUsers = false;\n  users.users.exp = {",
            "  users.users.exp = {",
        ))
        assert result["decision"] == "block"

    def test_4_password_equals_change(self):
        result = run_main(edit_input(
            CONFIG,
            '    password = "pa";',
            '    password = "changed";',
        ))
        assert result["decision"] == "block"

    def test_5_multi_protected_partial_change(self):
        old = (
            "  systemd.sysusers.enable = false;\n"
            "  users.mutableUsers = false;\n"
            "  users.users.exp = {"
        )
        new = (
            "  systemd.sysusers.enable = false;\n"
            "  users.users.exp = {"
        )
        result = run_main(edit_input(CONFIG, old, new))
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Edit — should pass
# ---------------------------------------------------------------------------

class TestEditPass:
    def test_6_non_protected_line(self):
        result = run_main(edit_input(
            CONFIG,
            "    shell = pkgs.zsh;",
            "    shell = pkgs.bash;",
        ))
        assert result is None

    def test_7_different_file(self):
        result = run_main(edit_input(
            "home/home.nix",
            "  systemd.sysusers.enable = false;",
            "  systemd.sysusers.enable = true;",
        ))
        assert result is None

    def test_8_protected_line_unchanged_context_changed(self):
        old = (
            "  # comment\n"
            "  systemd.sysusers.enable = false;\n"
            "  users.users.exp = {"
        )
        new = (
            "  # updated comment\n"
            "  systemd.sysusers.enable = false;\n"
            "  users.users.exp = {"
        )
        result = run_main(edit_input(CONFIG, old, new))
        assert result is None

    def test_9_empty_strings(self):
        result = run_main(edit_input(CONFIG, "", ""))
        assert result is None

    def test_10_hashed_password_file_detected(self):
        result = run_main(edit_input(
            CONFIG,
            '    hashedPasswordFile = "/etc/nixos/password-exp";',
            '    hashedPasswordFile = "/etc/nixos/other";',
        ))
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# Write — should block
# ---------------------------------------------------------------------------

class TestWriteBlock:
    def test_11_protected_line_removed(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        cfg.write_text(
            "  systemd.sysusers.enable = false;\n"
            "  users.users.exp = {\n"
            "    shell = pkgs.zsh;\n"
            "  };\n"
        )
        result = check_write({
            "file_path": str(cfg),
            "content": (
                "  users.users.exp = {\n"
                "    shell = pkgs.zsh;\n"
                "  };\n"
            ),
        })
        assert result is not None
        assert "sysusers" in result

    def test_12_protected_value_changed(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        cfg.write_text('    initialPassword = "pa";\n')
        result = check_write({
            "file_path": str(cfg),
            "content": '    initialPassword = "changed";\n',
        })
        assert result is not None
        assert "initialPassword" in result


# ---------------------------------------------------------------------------
# Write — should pass
# ---------------------------------------------------------------------------

class TestWritePass:
    def test_13_protected_lines_preserved(self, tmp_path):
        content = (
            "  systemd.sysusers.enable = false;\n"
            '    initialPassword = "pa";\n'
        )
        cfg = tmp_path / "configuration.nix"
        cfg.write_text(content)
        result = check_write({"file_path": str(cfg), "content": content})
        assert result is None

    def test_14_new_file(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        result = check_write({
            "file_path": str(cfg),
            "content": "  systemd.sysusers.enable = true;\n",
        })
        assert result is None

    def test_15_different_file(self, tmp_path):
        other = tmp_path / "home.nix"
        other.write_text("  systemd.sysusers.enable = false;\n")
        result = check_write({
            "file_path": str(other),
            "content": "  systemd.sysusers.enable = true;\n",
        })
        assert result is None


# ---------------------------------------------------------------------------
# Other edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_16_irrelevant_tool(self):
        result = run_main({
            "tool_name": "Read",
            "tool_input": {"file_path": CONFIG},
        })
        assert result is None

    def test_17_empty_file_path(self):
        result = run_main(edit_input(
            "",
            "  systemd.sysusers.enable = false;",
            "  systemd.sysusers.enable = true;",
        ))
        assert result is None
