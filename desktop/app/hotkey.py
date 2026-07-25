"""
Global hotkey listener using pynput.
Listens for a configurable hotkey combo (e.g. Ctrl+Space).
On press → starts recording. On release → stops and triggers processing.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from app.config import config

logger = logging.getLogger(__name__)

# ── Key mapping ─────────────────────────────────────────────────────────────────

_MODIFIER_MAP: dict[str, Key] = {
    "ctrl": Key.ctrl_l,
    "ctrl_l": Key.ctrl_l,
    "ctrl_r": Key.ctrl_r,
    "alt": Key.alt_l,
    "alt_l": Key.alt_l,
    "alt_r": Key.alt_r,
    "shift": Key.shift_l,
    "shift_l": Key.shift_l,
    "shift_r": Key.shift_r,
    "cmd": Key.cmd,
    "command": Key.cmd,
    "super": Key.cmd,
    "win": Key.cmd,
}

_SPECIAL_KEY_MAP: dict[str, Key] = {
    "space": Key.space,
    "tab": Key.tab,
    "enter": Key.enter,
    "esc": Key.esc,
    "escape": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}


def _parse_hotkey(combo_str: str) -> tuple[set[Key], Key | KeyCode]:
    """
    Parse a hotkey string like 'ctrl+space' into modifiers and a trigger key.

    Returns:
        (set of modifier Keys, trigger Key or KeyCode)
    """
    parts = [p.strip().lower() for p in combo_str.split("+")]
    if len(parts) < 2:
        raise ValueError(f"Hotkey must have at least modifier+key, got: '{combo_str}'")

    modifiers: set[Key] = set()
    trigger: Key | KeyCode | None = None

    for i, part in enumerate(parts):
        if part in _MODIFIER_MAP:
            modifiers.add(_MODIFIER_MAP[part])
        elif part in _SPECIAL_KEY_MAP:
            trigger = _SPECIAL_KEY_MAP[part]
        elif len(part) == 1:
            trigger = KeyCode.from_char(part)
        else:
            raise ValueError(f"Unknown key in hotkey: '{part}'")

    if trigger is None:
        raise ValueError(f"No trigger key found in hotkey: '{combo_str}'")
    if not modifiers:
        raise ValueError(f"No modifier keys found in hotkey: '{combo_str}'")

    return modifiers, trigger


class HotkeyListener:
    """
    Global hotkey listener.

    Calls on_press_callback when the hotkey is pressed down,
    and on_release_callback when the trigger key is released.
    """

    def __init__(
        self,
        on_press_callback: Callable[[], None],
        on_release_callback: Callable[[], None],
    ) -> None:
        self._on_press = on_press_callback
        self._on_release = on_release_callback
        self._listener: keyboard.Listener | None = None

        # Parse the configured hotkey
        self._modifiers, self._trigger = _parse_hotkey(config.hotkey_combo)
        logger.info(
            "Hotkey configured: %s (modifiers=%s, trigger=%s)",
            config.hotkey_combo,
            self._modifiers,
            self._trigger,
        )

        # Track currently pressed keys
        self._pressed_keys: set[Key | KeyCode] = set()
        self._is_active = False  # Whether the hotkey is currently held
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start listening for the global hotkey. Runs in its own thread."""
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("🎧 Hotkey listener started. Press %s to record.", config.hotkey_combo)

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped.")

    def _handle_press(self, key: Key | KeyCode | None) -> None:
        """Track key presses and detect when the full combo is held."""
        if key is None:
            return

        # Normalize: map right-side modifiers to their left equivalents
        normalized = self._normalize_key(key)
        self._pressed_keys.add(normalized)

        with self._lock:
            if not self._is_active and self._is_hotkey_pressed():
                self._is_active = True
                logger.debug("Hotkey pressed — starting recording.")
                try:
                    self._on_press()
                except Exception as e:
                    logger.error("on_press callback error: %s", e, exc_info=True)

    def _handle_release(self, key: Key | KeyCode | None) -> None:
        """Detect when the trigger key is released while hotkey was active."""
        if key is None:
            return

        normalized = self._normalize_key(key)

        with self._lock:
            if self._is_active and normalized == self._trigger:
                self._is_active = False
                logger.debug("Trigger key released — stopping recording.")
                try:
                    self._on_release()
                except Exception as e:
                    logger.error("on_release callback error: %s", e, exc_info=True)

        self._pressed_keys.discard(normalized)

    def _is_hotkey_pressed(self) -> bool:
        """Check if all modifier keys and the trigger key are currently pressed."""
        return (
            self._modifiers.issubset(self._pressed_keys)
            and self._trigger in self._pressed_keys
        )

    def _normalize_key(self, key: Key | KeyCode) -> Key | KeyCode:
        """Normalize right-side modifiers to left-side equivalents."""
        mapping = {
            Key.ctrl_r: Key.ctrl_l,
            Key.alt_r: Key.alt_l,
            Key.shift_r: Key.shift_l,
        }
        if isinstance(key, Key):
            return mapping.get(key, key)
        return key
