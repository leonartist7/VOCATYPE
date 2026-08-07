"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Ensure config settings are re-read per test module."""
    from app.config import get_settings
    from app.middleware import _rate_buckets

    get_settings.cache_clear()
    _rate_buckets.clear()
    yield
    get_settings.cache_clear()
    _rate_buckets.clear()
