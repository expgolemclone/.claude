"""Tests for post-verify-protected-nix-config.py hook."""

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("post-verify-protected-nix-config")
extract_protected_lines = mod.extract_protected_lines
compute_hash = mod.compute_hash
main = mod.main

GOOD_CONFIG = """\
  # --- ユーザー ---
  systemd.sysusers.enable = false;
  users.users.exp = {
    isNormalUser = true;
    description = "exp";
    extraGroups = [ "networkmanager" "wheel" ];
    shell = pkgs.zsh;
    initialPassword = "pa";
  };
"""

CHANGED_CONFIG = """\
  # --- ユーザー ---
  systemd.sysusers.enable = true;
  users.users.exp = {
    isNormalUser = true;
    description = "exp";
    extraGroups = [ "networkmanager" "wheel" ];
    shell = pkgs.zsh;
    initialPassword = "pa";
  };
"""

REMOVED_LINE_CONFIG = """\
  # --- ユーザー ---
  users.users.exp = {
    isNormalUser = true;
    description = "exp";
    extraGroups = [ "networkmanager" "wheel" ];
    shell = pkgs.zsh;
    initialPassword = "pa";
  };
"""

NO_PROTECTED_CONFIG = """\
  networking.hostName = "nixos";
  time.timeZone = "Asia/Tokyo";
"""


# ---------------------------------------------------------------------------
# extract_protected_lines
# ---------------------------------------------------------------------------

class TestExtract:
    def test_1_finds_protected_lines(self):
        lines = extract_protected_lines(GOOD_CONFIG)
        assert any("sysusers" in l for l in lines)
        assert any("initialPassword" in l for l in lines)

    def test_2_no_protected_lines(self):
        lines = extract_protected_lines(NO_PROTECTED_CONFIG)
        assert lines == []

    def test_3_sorted_output(self):
        lines = extract_protected_lines(GOOD_CONFIG)
        assert lines == sorted(lines)


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------

class TestHash:
    def test_4_same_lines_same_hash(self):
        lines = ["a", "b"]
        assert compute_hash(lines) == compute_hash(lines)

    def test_5_different_lines_different_hash(self):
        assert compute_hash(["a"]) != compute_hash(["b"])


# ---------------------------------------------------------------------------
# main — first run (no hash file)
# ---------------------------------------------------------------------------

class TestFirstRun:
    def test_6_creates_hash_file(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        cfg.write_text(GOOD_CONFIG)
        hash_file = tmp_path / "hash"

        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()

        assert hash_file.exists()
        assert len(hash_file.read_text().strip()) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# main — hash matches (no change)
# ---------------------------------------------------------------------------

class TestNoChange:
    def test_7_passes_when_unchanged(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        cfg.write_text(GOOD_CONFIG)
        hash_file = tmp_path / "hash"
        lines = extract_protected_lines(GOOD_CONFIG)
        hash_file.write_text(compute_hash(lines))

        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()  # should not raise


# ---------------------------------------------------------------------------
# main — hash mismatch (change detected)
# ---------------------------------------------------------------------------

class TestChangeDetected:
    def test_8_blocks_when_value_changed(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        hash_file = tmp_path / "hash"

        cfg.write_text(GOOD_CONFIG)
        lines = extract_protected_lines(GOOD_CONFIG)
        hash_file.write_text(compute_hash(lines))

        cfg.write_text(CHANGED_CONFIG)

        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_9_blocks_when_line_removed(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        hash_file = tmp_path / "hash"

        cfg.write_text(GOOD_CONFIG)
        lines = extract_protected_lines(GOOD_CONFIG)
        hash_file.write_text(compute_hash(lines))

        cfg.write_text(REMOVED_LINE_CONFIG)

        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_10_config_not_found(self, tmp_path):
        cfg = tmp_path / "nonexistent.nix"
        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()  # should not raise

    def test_11_no_protected_lines_in_config(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        cfg.write_text(NO_PROTECTED_CONFIG)
        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()  # should not raise

    def test_12_hash_file_deleted_resets(self, tmp_path):
        cfg = tmp_path / "configuration.nix"
        hash_file = tmp_path / "hash"

        cfg.write_text(GOOD_CONFIG)
        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()
        assert hash_file.exists()

        cfg.write_text(CHANGED_CONFIG)
        hash_file.unlink()

        with mock.patch.object(mod, "CONFIG_PATH", cfg), \
             mock.patch.object(mod, "HASH_FILE", hash_file), \
             mock.patch("sys.stdin.read", return_value="{}"):
            main()  # should not raise, creates new hash

        assert hash_file.exists()
