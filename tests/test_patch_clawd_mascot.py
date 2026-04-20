"""Tests for scripts/patch-clawd-mascot.py."""

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "patch-clawd-mascot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("patch_clawd_mascot", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
        Path(
            "AppData/Roaming/npm/node_modules/@anthropic-ai/.claude-code-tySWtmFC/bin/claude.exe"
        ),
    ],
)
def test_find_targets_detects_windows_npm_installs(tmp_path, monkeypatch, relative_path):
    module = load_module()
    home = tmp_path / "home"
    target = home / relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"")

    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(module.Path, "home", lambda: home)

    assert target in module.find_targets()


def test_patch_binary_applies_windows_specific_pairs(tmp_path):
    module = load_module()
    target = tmp_path / "claude.exe"
    target.write_bytes(
        b"\0".join(
            [
                b'rgb(215,119,87)',
                b'color:"error",external:"bypassPermissions"',
                b'A3.createElement(v,{bold:!0,color:"claude"},_)',
                b'let UH=Me8(q);if(',
                b'let DH=Me8(q),OH=',
            ]
        )
    )

    assert module.patch_binary(target) is True

    data = target.read_bytes()
    assert b"rgb(215,119,87)" not in data
    assert b"rgb(000,000,00)" in data
    assert b'color:"error",external:"bypassPermissions"' not in data
    assert b'color:"cyan", external:"bypassPermissions"' in data
    assert b'A3.createElement(v,{bold:!0,color:"claude"},_)' not in data
    assert b'A3.createElement(v,{bold:!0,color:"black" },_)' in data
    assert b'let UH=Me8(q);if(' not in data
    assert b'let UH=""    ;if(' in data
    assert b'let DH=Me8(q),OH=' not in data
    assert b'let DH=""    ,OH=' in data


def test_patch_binary_is_idempotent_with_windows_specific_pairs(tmp_path, capsys):
    module = load_module()
    target = tmp_path / "claude.exe"
    target.write_bytes(
        b"\0".join(
            [
                b'rgb(000,000,00)',
                b'clawd_body:"rgb(00,00,000)"',
                b'claude:"rgb(00,00,000)"',
                b'color:"cyan", external:"bypassPermissions"',
                b'A3.createElement(v,{bold:!0,color:"black" },_)',
                b'let UH=""    ;if(',
                b'let DH=""    ,OH=',
            ]
        )
    )

    assert module.patch_binary(target) is True

    captured = capsys.readouterr()
    assert "既にパッチ済みです。" in captured.out
