"""
Text injector — copies processed text to the clipboard and simulates a paste keystroke.
"""

from __future__ import annotations

import logging
import platform
import time

import pyautogui
import pyperclip

from app.config import config

logger = logging.getLogger(__name__)

# Prevent pyautogui from throwing on edge-of-screen mouse positions
pyautogui.FAILSAFE = False


def inject_text(text: str) -> bool:
    """
    Inject text into the currently focused field by:
    1. Copying text to the system clipboard.
    2. Waiting 100ms for the clipboard to register.
    3. Simulating Ctrl+V (or Cmd+V on macOS).

    Args:
        text: The processed text to inject.

    Returns:
        True if injection succeeded, False otherwise.
    """
    if not text or not text.strip():
        logger.warning("Empty text — nothing to inject.")
        return False

    try:
        # Step 1: Copy to clipboard
        pyperclip.copy(text)
        logger.debug("Copied %d chars to clipboard.", len(text))

        # Step 2: Wait for clipboard to register
        time.sleep(0.1)

        # Step 3: Simulate paste
        hotkey = config.paste_hotkey
        logger.info("Pasting via hotkey: %s", "+".join(hotkey))
        pyautogui.hotkey(*hotkey)

        logger.info("✅ Text injected successfully (%d chars).", len(text))
        return True

    except pyperclip.PyperclipException as e:
        logger.error("Clipboard error: %s", e)
        _fallback_type(text)
        return True
    except Exception as e:
        logger.error("Injection failed: %s", e, exc_info=True)
        return False


def _fallback_type(text: str) -> None:
    """
    Fallback: type the text character by character using pyautogui.
    Much slower but works even if clipboard fails.
    """
    logger.warning("Falling back to character-by-character typing.")
    try:
        # pyautogui.write doesn't handle unicode well, so use typewrite for ASCII
        # and hotkey for special chars
        pyautogui.write(text, interval=0.01)
        logger.info("Fallback typing completed.")
    except Exception as e:
        logger.error("Fallback typing also failed: %s", e)
