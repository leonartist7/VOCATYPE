"""Unit tests for the desktop client configuration."""

from __future__ import annotations

import sys

from app.config import Config, config


class TestConfigDefaults:
    def test_defaults(self) -> None:
        assert config.backend_url == "http://localhost:8000"
        assert config.hotkey_combo == "ctrl+space"
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.chunk_size == 1024
        assert config.sample_width == 2


class TestConfigPlatform:
    def test_windows_paste_hotkey(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        c = Config()
        assert c.platform == "windows"
        assert c.paste_hotkey == ["ctrl", "v"]

    def test_macos_paste_hotkey(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        c = Config()
        assert c.platform == "macos"
        assert c.paste_hotkey == ["command", "v"]

    def test_linux_platform(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        c = Config()
        assert c.platform == "linux"
        assert c.paste_hotkey == ["ctrl", "v"]


class TestConfigEnvOverride:
    def test_env_overrides_apply(self, monkeypatch) -> None:
        monkeypatch.setenv("BACKEND_URL", "http://example.com:9999")
        monkeypatch.setenv("HOTKEY_COMBO", "alt+space")
        c = Config()
        assert c.backend_url == "http://example.com:9999"
        assert c.hotkey_combo == "alt+space"
