"""Tests for block-nixos-rebuild-protected-changes.py hook."""

import importlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from tests.conftest import HOOKS_DIR

sys.path.insert(0, str(HOOKS_DIR))
mod = importlib.import_module("block-nixos-rebuild-protected-changes")
check_config_diff = mod.check_config_diff
check_mkforce_override = mod.check_mkforce_override
main = mod.main


def run_main(command: str, diff_output: str = "") -> dict | None:
    stdin_data = {"tool_input": {"command": command}}
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            with mock.patch.object(mod, "get_diff", return_value=diff_output):
                main()
        raw = out.getvalue()
        return json.loads(raw) if raw else None


DIFF_SYSUSERS_CHANGED = """\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -156,7 +156,7 @@
   # --- ユーザー ---
-  systemd.sysusers.enable = false;
+  systemd.sysusers.enable = true;
   users.users.exp = {
"""

DIFF_PASSWORD_REMOVED = """\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -160,7 +160,6 @@
     extraGroups = [ "networkmanager" "wheel" ];
     shell = pkgs.zsh;
-    initialPassword = "pa";
   };
"""

DIFF_MUTABLE_USERS_ADDED = """\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -156,6 +156,7 @@
   # --- ユーザー ---
   systemd.sysusers.enable = false;
+  users.mutableUsers = false;
   users.users.exp = {
"""

DIFF_SAFE_CHANGE = """\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -170,7 +170,7 @@
   fonts.packages = with pkgs; [
-    noto-fonts
+    noto-fonts-cjk-sans
   ];
"""

DIFF_OTHER_FILE = """\
diff --git a/home/home.nix b/home/home.nix
--- a/home/home.nix
+++ b/home/home.nix
@@ -1,3 +1,3 @@
-  password = "old";
+  password = "new";
"""

DIFF_MKFORCE_OVERRIDE = """\
diff --git a/hosts/nixos/configuration.nix b/hosts/nixos/configuration.nix
--- a/hosts/nixos/configuration.nix
+++ b/hosts/nixos/configuration.nix
@@ -156,6 +156,9 @@
+{ lib, ... }: {
+  systemd.sysusers.enable = lib.mkForce true;
+}
"""

DIFF_MKFORCE_SAFE = """\
diff --git a/modules/safe.nix b/modules/safe.nix
--- /dev/null
+++ b/modules/safe.nix
@@ -0,0 +1,3 @@
+{ lib, ... }: {
+  services.nginx.enable = lib.mkForce true;
+}
"""


# ---------------------------------------------------------------------------
# nixos-rebuild detection
# ---------------------------------------------------------------------------

class TestCommandDetection:
    def test_1_non_rebuild_command_passes(self):
        result = run_main("git status", DIFF_SYSUSERS_CHANGED)
        assert result is None

    def test_2_rebuild_switch_detected(self):
        result = run_main("nixos-rebuild switch --flake .", DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"

    def test_3_rebuild_build_detected(self):
        result = run_main("nixos-rebuild build", DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"

    def test_4_sudo_rebuild_detected(self):
        result = run_main("sudo nixos-rebuild switch", DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"


# ---------------------------------------------------------------------------
# config diff — should block
# ---------------------------------------------------------------------------

class TestConfigDiffBlock:
    def test_5_sysusers_changed(self):
        result = check_config_diff(DIFF_SYSUSERS_CHANGED)
        assert result is not None
        assert "sysusers" in result

    def test_6_password_removed(self):
        result = check_config_diff(DIFF_PASSWORD_REMOVED)
        assert result is not None
        assert "initialPassword" in result

    def test_7_mutable_users_added(self):
        result = check_config_diff(DIFF_MUTABLE_USERS_ADDED)
        assert result is not None
        assert "mutableUsers" in result


# ---------------------------------------------------------------------------
# config diff — should pass
# ---------------------------------------------------------------------------

class TestConfigDiffPass:
    def test_8_safe_change(self):
        result = check_config_diff(DIFF_SAFE_CHANGE)
        assert result is None

    def test_9_other_file_with_keyword(self):
        result = check_config_diff(DIFF_OTHER_FILE)
        assert result is None

    def test_10_empty_diff(self):
        result = check_config_diff("")
        assert result is None


# ---------------------------------------------------------------------------
# mkForce override
# ---------------------------------------------------------------------------

class TestMkForceOverride:
    def test_11_mkforce_with_protected_keyword(self):
        result = check_mkforce_override(DIFF_MKFORCE_OVERRIDE)
        assert result is not None
        assert "mkForce" in result

    def test_12_mkforce_with_safe_keyword(self):
        result = check_mkforce_override(DIFF_MKFORCE_SAFE)
        assert result is None


# ---------------------------------------------------------------------------
# Integration via main()
# ---------------------------------------------------------------------------

class TestMainIntegration:
    def test_13_rebuild_with_no_diff(self):
        result = run_main("nixos-rebuild switch", "")
        assert result is None

    def test_14_rebuild_with_safe_diff(self):
        result = run_main("nixos-rebuild switch", DIFF_SAFE_CHANGE)
        assert result is None

    def test_15_rebuild_with_protected_diff(self):
        result = run_main("nixos-rebuild switch", DIFF_SYSUSERS_CHANGED)
        assert result["decision"] == "block"

    def test_16_rebuild_with_mkforce(self):
        result = run_main("nixos-rebuild switch", DIFF_MKFORCE_OVERRIDE)
        assert result["decision"] == "block"

    def test_17_rebuild_with_both_safe_and_protected(self):
        combined = DIFF_SAFE_CHANGE + "\n" + DIFF_SYSUSERS_CHANGED
        result = run_main("nixos-rebuild switch", combined)
        assert result["decision"] == "block"
