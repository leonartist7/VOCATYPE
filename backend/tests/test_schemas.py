"""Unit tests for the Pydantic request/response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import AudioContext, ErrorResponse, ProcessedResponse


class TestAudioContext:
    def test_defaults(self) -> None:
        ctx = AudioContext()
        assert ctx.app_name == "unknown"
        assert ctx.platform == "unknown"
        assert ctx.selected_text is None
        assert ctx.language == "en"

    def test_full_payload(self) -> None:
        ctx = AudioContext(
            app_name="com.whatsapp",
            platform="android",
            selected_text="hello",
            language="es",
        )
        assert ctx.app_name == "com.whatsapp"
        assert ctx.selected_text == "hello"
        assert ctx.language == "es"

    def test_extra_fields_ignored(self) -> None:
        ctx = AudioContext(app_name="x", unknown_field=123)
        assert ctx.app_name == "x"


class TestProcessedResponse:
    def test_valid(self) -> None:
        resp = ProcessedResponse(
            processed_text="Clean text.",
            raw_transcript="Clean text.",
        )
        assert resp.tone_applied == "neutral"

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessedResponse(processed_text="only")

    def test_custom_tone(self) -> None:
        resp = ProcessedResponse(
            processed_text="t",
            raw_transcript="r",
            tone_applied="casual",
        )
        assert resp.tone_applied == "casual"


class TestErrorResponse:
    def test_minimal(self) -> None:
        err = ErrorResponse(error="boom")
        assert err.detail is None

    def test_full(self) -> None:
        err = ErrorResponse(error="boom", detail="something failed")
        assert err.detail == "something failed"
