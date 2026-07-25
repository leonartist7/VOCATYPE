"""
Active window context detection.
Reads the currently focused window title to determine what app the user is in,
so Gemini can adapt the tone of its output.
"""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def get_active_window_context() -> dict[str, str]:
    """
    Get the active window title and infer app context.

    Returns:
        Dict with keys: app_name, platform.
    """
    platform = _get_platform()
    title = ""

    try:
        if platform == "windows":
            title = _get_active_window_windows()
        elif platform == "macos":
            title = _get_active_window_macos()
        else:
            title = _get_active_window_linux()
    except Exception as e:
        logger.warning("Failed to detect active window: %s", e)
        title = "unknown"

    logger.info("Active window: '%s' (platform=%s)", title, platform)

    return {
        "app_name": title,
        "platform": platform,
    }


def _get_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform == "win32":
        return "windows"
    return "linux"


def _get_active_window_windows() -> str:
    """Get the active window title on Windows using ctypes."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # Get foreground window handle
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"

        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return "unknown"

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Also try to get the process name for better context
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                buf_size = wintypes.DWORD(260)
                exe_buf = ctypes.create_unicode_buffer(260)
                kernel32.QueryFullProcessImageNameW(handle, 0, exe_buf, ctypes.byref(buf_size))
                kernel32.CloseHandle(handle)
                exe_name = exe_buf.value.split("\\")[-1] if exe_buf.value else ""
                if exe_name:
                    return f"{exe_name} - {title}"
        except Exception:
            pass  # Fall through to just the title

        return title if title else "unknown"

    except Exception as e:
        logger.warning("Windows active window detection failed: %s", e)
        return "unknown"


def _get_active_window_macos() -> str:
    """Get the active window title on macOS using AppleScript."""
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            set windowTitle to ""
            try
                set windowTitle to name of front window of (first application process whose frontmost is true)
            end try
            return frontApp & " - " & windowTitle
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "unknown"
    except subprocess.TimeoutExpired:
        logger.warning("AppleScript timed out getting active window")
        return "unknown"
    except FileNotFoundError:
        logger.warning("osascript not found — not running on macOS?")
        return "unknown"


def _get_active_window_linux() -> str:
    """Get the active window title on Linux using xdotool."""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "unknown"
    except FileNotFoundError:
        logger.warning("xdotool not found. Install with: sudo apt install xdotool")
        return "unknown"
    except subprocess.TimeoutExpired:
        return "unknown"
