"""Shared pytest fixtures for the desktop client test suite."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_pyaudio(monkeypatch):
    """Provide a stub `pyaudio` module so tests run without native PortAudio.

    The real `app.recorder` lazily imports pyaudio, but providing a lightweight
    stub makes tests hermetic and platform-independent.
    """
    stub = types.ModuleType("pyaudio")

    class _StubPyAudio:
        def __init__(self):
            self.stream = None

        def open(self, *args, **kwargs):
            stream = _StubStream()
            self.stream = stream
            return stream

        def terminate(self):
            pass

    class _StubStream:
        def __init__(self):
            self._active = False

        def start_stream(self):
            self._active = True

        def stop_stream(self):
            self._active = False

        def close(self):
            self._active = False

        def is_active(self):
            return self._active

    stub.PyAudio = _StubPyAudio
    stub.Stream = _StubStream
    stub.paInt16 = 8
    stub.paContinue = 1
    stub.paComplete = 0

    monkeypatch.setitem(sys.modules, "pyaudio", stub)
    yield stub


@pytest.fixture(autouse=True)
def _reset_api_client(monkeypatch):
    """Ensure the persistent HTTP client is recreated per test."""
    from app import api_client

    monkeypatch.setattr(api_client, "_client", None)
    yield

