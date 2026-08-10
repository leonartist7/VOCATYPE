"""
Pydantic models for request/response validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioContext(BaseModel):
    """Context payload sent alongside the audio file."""

    app_name: str = Field(
        default="unknown",
        description="Package name or window title of the active application.",
    )
    platform: str = Field(
        default="unknown",
        description="Client platform: 'android', 'windows', or 'macos'.",
    )
    selected_text: str | None = Field(
        default=None,
        description="Text currently selected in the active field. "
        "If present, audio is treated as a command to transform this text.",
    )
    language: str = Field(
        default="en",
        description="ISO 639-1 language code for the spoken audio.",
    )


class ProcessedResponse(BaseModel):
    """Response returned after the transcription engine processes the audio."""

    processed_text: str = Field(
        description="Final cleaned, formatted text ready for insertion. "
        "Whisper returns the raw transcription.",
    )
    raw_transcript: str = Field(
        description="Raw transcription before intelligent processing. "
        "Same as processed_text when using whisper.",
    )
    tone_applied: str = Field(
        default="neutral",
        description="Tone that was applied: 'casual', 'professional', 'neutral', or 'none' (whisper).",
    )
    cleaning_error: str | None = Field(
        default=None,
        description="Set when online cleaning (DeepSeek) failed and the raw "
        "transcript was returned instead — dictation still works, just unpolished.",
    )


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: str
    detail: str | None = None
