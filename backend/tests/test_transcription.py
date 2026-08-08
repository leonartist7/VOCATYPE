"""Unit tests for the transcription service (MIME detection, size validation, audio parts)."""

from __future__ import annotations

import pytest

from app.services.transcription import (
    _get_extension,
    detect_mime_type,
    validate_audio_size,
)


class TestGetExtension:
    def test_standard_extension(self) -> None:
        assert _get_extension("recording.wav") == ".wav"

    def test_uppercase_extension_lowercased(self) -> None:
        assert _get_extension("Recording.WAV") == ".wav"

    def test_multiple_dots(self) -> None:
        assert _get_extension("my.file.name.m4a") == ".m4a"

    def test_no_extension(self) -> None:
        assert _get_extension("recording") == ""


class TestDetectMimeType:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("clip.wav", "audio/wav"),
            ("clip.wave", "audio/wav"),
            ("clip.mp3", "audio/mp3"),
            ("clip.m4a", "audio/mp4"),
            ("clip.mp4", "audio/mp4"),
            ("clip.ogg", "audio/ogg"),
            ("clip.oga", "audio/ogg"),
            ("clip.webm", "audio/webm"),
            ("clip.flac", "audio/flac"),
            ("clip.aac", "audio/aac"),
            ("clip.3gp", "audio/3gpp"),
        ],
    )
    def test_known_extensions(self, filename: str, expected: str) -> None:
        assert detect_mime_type(filename) == expected

    def test_content_type_used_when_extension_unknown(self) -> None:
        assert detect_mime_type("clip.xyz", "audio/webm") == "audio/webm"

    def test_content_type_prefers_valid_audio(self) -> None:
        assert detect_mime_type("clip.xyz", "video/mp4") == "audio/wav"

    def test_unknown_filename_falls_back(self) -> None:
        assert detect_mime_type("clip.bin") == "audio/wav"

    def test_empty_filename_falls_back(self) -> None:
        assert detect_mime_type("") == "audio/wav"


class TestValidateAudioSize:
    def test_under_limit_passes(self) -> None:
        validate_audio_size(b"\x00" * 1024)  # 1KB

    def test_exactly_at_limit_passes(self) -> None:
        validate_audio_size(b"\x00" * (20 * 1024 * 1024))  # exactly 20MB

    def test_over_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="too large"):
            validate_audio_size(b"\x00" * (21 * 1024 * 1024))

    def test_custom_limit(self) -> None:
        with pytest.raises(ValueError, match="too large"):
            validate_audio_size(b"\x00" * 2048, max_size_mb=0.001)
