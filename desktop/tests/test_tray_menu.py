"""Regression tests for the system tray menu construction."""

from __future__ import annotations

import sys
import types


def _make_fake_pystray() -> types.ModuleType:
    """A minimal pystray stand-in that mimics the real callback signatures.

    In real pystray:
      - a MenuItem's `checked` callback is invoked as `callback(item)`
      - action callbacks receive `(icon, item)`
    This fake builds the menu the same way real pystray does, so signature
    mistakes (e.g. a `checked` lambda expecting `(icon, item)`) surface here.
    """

    class MenuItem:
        def __init__(self, text, action=None, checked=None, enabled=True):
            self.text = text
            self.action = action
            self.checked = checked
            self.enabled = enabled
            if checked is not None:
                self.checked_state = checked(self)

        def __repr__(self):
            return f"MenuItem({self.text!r})"

    class Menu:
        SEPARATOR = object()

        def __init__(self, *items):
            self.items = items

    class Icon:
        def __init__(self, name, icon, title, menu):
            self.name = name
            self.icon = icon
            self.title = title
            self.menu = menu
            self.stopped = False

        def stop(self):
            self.stopped = True

    fake = types.ModuleType("pystray")
    fake.MenuItem = MenuItem
    fake.Menu = Menu
    fake.Icon = Icon
    return fake


def test_create_tray_icon_builds_menu_with_valid_callbacks(monkeypatch):
    """The tray menu must construct without errors using pystray signatures.

    Regression: the "Launch at login" checked callback used to be defined as
    `lambda icon, item: ...`, which raised `TypeError: missing 1 required
    positional argument: 'item'` the moment pystray built the menu.
    """
    import app.main as main

    fake = _make_fake_pystray()
    monkeypatch.setitem(sys.modules, "pystray", fake)
    monkeypatch.setattr(main.autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(main, "load_or_create_icon", lambda recording=False: "icon")

    icon = main._create_tray_icon()
    assert icon is not None
    assert icon.name == "vocatype"
    assert icon.title == "Vocatype (ctrl+space)"

    separator = fake.Menu.SEPARATOR
    items = [i for i in icon.menu.items if i is not separator]
    labels = [i.text for i in items]
    assert "Vocatype — ctrl+space" in labels
    assert "Launch at login" in labels
    assert "Quit" in labels

    launch = next(i for i in items if i.text == "Launch at login")
    assert launch.checked_state is False

    quit_item = next(i for i in items if i.text == "Quit")
    assert callable(quit_item.action)
    quit_item.action(icon, quit_item)
