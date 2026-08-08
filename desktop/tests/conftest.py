"""Shared pytest fixtures for the desktop client test suite."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_sounddevice(monkeypatch):
    """Provide a stub `sounddevice` module so tests run without native PortAudio.

    The real `app.recorder` lazily imports sounddevice, but providing a
    lightweight stub makes tests hermetic and platform-independent.
    """
    stub = types.ModuleType("sounddevice")

    class _StubStream:
        def __init__(
            self,
            samplerate=None,
            blocksize=None,
            device=None,
            channels=None,
            dtype=None,
            latency=None,
            extra_settings=None,
            callback=None,
            finished_callback=None,
            **kwargs,
        ):
            self._active = False
            self.callback = callback
            self.kwargs = {
                "samplerate": samplerate,
                "blocksize": blocksize,
                "channels": channels,
                "dtype": dtype,
                "callback": callback,
            }

        @property
        def active(self):
            return self._active

        def start(self):
            self._active = True

        def stop(self):
            self._active = False

        def close(self):
            self._active = False

    last_open = {}

    def _open(**kwargs):
        last_open.update(kwargs)
        return _StubStream(**kwargs)

    stub.RawInputStream = _open
    stub.last_open = last_open

    monkeypatch.setitem(sys.modules, "sounddevice", stub)
    yield stub


@pytest.fixture(autouse=True)
def _reset_api_client(monkeypatch):
    """Ensure the persistent HTTP client is recreated per test."""
    from app import api_client

    monkeypatch.setattr(api_client, "_client", None)
    yield
