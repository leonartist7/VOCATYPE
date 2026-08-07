"""Unit tests for the desktop client's global hotkey parsing and listener."""

from __future__ import annotations

import pytest
from pynput.keyboard import Key, KeyCode

from app.hotkey import _parse_hotkey


class TestParseHotkey:
    def test_ctrl_space(self) -> None:
        modifiers, trigger = _parse_hotkey("ctrl+space")
        assert Key.ctrl_l in modifiers
        assert trigger == Key.space

    def test_cmd_option_aliases(self) -> None:
        for alias in ("cmd", "command", "super", "win"):
            modifiers, _ = _parse_hotkey(f"{alias}+f1")
            assert Key.cmd in modifiers

    def test_single_char_trigger(self) -> None:
        modifiers, trigger = _parse_hotkey("alt+a")
        assert Key.alt_l in modifiers
        assert isinstance(trigger, KeyCode)
        assert trigger.char == "a"

    def test_shift_and_fkey(self) -> None:
        modifiers, trigger = _parse_hotkey("shift+f5")
        assert Key.shift_l in modifiers
        assert trigger == Key.f5

    def test_multiple_modifiers(self) -> None:
        modifiers, trigger = _parse_hotkey("ctrl+alt+enter")
        assert Key.ctrl_l in modifiers
        assert Key.alt_l in modifiers
        assert trigger == Key.enter

    def test_uppercase_parsed_lowercase(self) -> None:
        modifiers, trigger = _parse_hotkey("CTRL+SPACE")
        assert Key.ctrl_l in modifiers
        assert trigger == Key.space

    def test_no_modifier_raises(self) -> None:
        with pytest.raises(ValueError, match="No modifier"):
            _parse_hotkey("space+enter")

    def test_no_trigger_raises(self) -> None:
        with pytest.raises(ValueError, match="No trigger"):
            _parse_hotkey("ctrl+shift")

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown key"):
            _parse_hotkey("ctrl+notakey")

    def test_single_part_raises(self) -> None:
        with pytest.raises(ValueError, match="at least modifier"):
            _parse_hotkey("space")
