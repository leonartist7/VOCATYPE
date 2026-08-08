"""
Auto-start registration for the Vocatype desktop client.

Registers the app to launch at login on Windows, macOS, and Linux so dictation
is always available. Uses the `appdirs`-independent approach: platform config
files + the current interpreter.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _startup_command() -> str:
    """Return the command used to launch this app."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        return sys.executable
    return f'"{sys.executable}" -m app.main'


def _windows_path() -> Path:
    """Path to the Windows startup shortcut."""
    import os

    startup = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    return startup / "vocatype.vbs"


def is_enabled() -> bool:
    """Check whether auto-start is currently enabled."""
    try:
        if sys.platform == "win32":
            return _windows_path().exists()
        if sys.platform == "darwin":
            plist = Path.home() / "Library" / "LaunchAgents" / "com.vocatype.agent.plist"
            return plist.exists()
        # Linux: check autostart desktop entry
        return (Path.home() / ".config" / "autostart" / "vocatype.desktop").exists()
    except Exception as e:
        logger.warning("Failed to check auto-start status: %s", e)
        return False


def enable() -> bool:
    """Enable launch-at-login. Returns True on success."""
    try:
        if sys.platform == "win32":
            _windows_path().parent.mkdir(parents=True, exist_ok=True)
            vbs = (
                'Set shell = CreateObject("WScript.Shell")\n'
                f'shell.Run "{_startup_command()}", 0, False\n'
            )
            _windows_path().write_text(vbs, encoding="utf-8")
            logger.info("Auto-start enabled (Windows).")
            return True

        if sys.platform == "darwin":
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            plist_dir.mkdir(parents=True, exist_ok=True)
            plist = plist_dir / "com.vocatype.agent.plist"
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vocatype.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>app.main</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            plist.write_text(content, encoding="utf-8")
            logger.info("Auto-start enabled (macOS).")
            return True

        # Linux
        desktop_dir = Path.home() / ".config" / "autostart"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        entry = desktop_dir / "vocatype.desktop"
        entry.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Vocatype\n"
            f"Exec={_startup_command()}\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
        logger.info("Auto-start enabled (Linux).")
        return True
    except Exception as e:
        logger.error("Failed to enable auto-start: %s", e)
        return False


def disable() -> bool:
    """Disable launch-at-login. Returns True on success."""
    try:
        if sys.platform == "win32":
            _windows_path().unlink(missing_ok=True)
        elif sys.platform == "darwin":
            (Path.home() / "Library" / "LaunchAgents" / "com.vocatype.agent.plist").unlink(
                missing_ok=True
            )
        else:
            (Path.home() / ".config" / "autostart" / "vocatype.desktop").unlink(missing_ok=True)
        logger.info("Auto-start disabled.")
        return True
    except Exception as e:
        logger.error("Failed to disable auto-start: %s", e)
        return False
