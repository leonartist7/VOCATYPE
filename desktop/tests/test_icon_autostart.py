"""Tests for the generated tray icon and auto-start helpers."""

from __future__ import annotations

import sys

from PIL import Image


def test_create_icon_returns_rgba_image():
    from app.icon import create_icon

    icon = create_icon(recording=False)
    assert isinstance(icon, Image.Image)
    assert icon.mode == "RGBA"

    recording = create_icon(recording=True)
    assert recording.mode == "RGBA"
    assert recording.getbbox() is not None


def test_icon_bytes_returns_valid_png():
    from app.icon import icon_bytes

    data = icon_bytes(recording=False)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_autostart_is_disabled_by_default(monkeypatch):
    """Fresh environment: auto-start should be reported as off."""
    import app.autostart as autostart

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "C:/fake/AppData")

    assert autostart.is_enabled() is False


def test_autostart_enable_creates_shortcut(tmp_path, monkeypatch):
    import app.autostart as autostart

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    startup = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    assert autostart.enable() is True
    assert (startup / "vocatype.vbs").exists()
    assert autostart.is_enabled() is True

    assert autostart.disable() is True
    assert not (startup / "vocatype.vbs").exists()
    assert autostart.is_enabled() is False
