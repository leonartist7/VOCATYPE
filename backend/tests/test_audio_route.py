"""Integration tests for the /process-audio and /health endpoints.

Uses FastAPI's TestClient with the Gemini service fully mocked.
"""

from __future__ import annotations

import io
import json
import wave

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import audio as audio_route


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def wav_bytes() -> bytes:
    """Generate a small valid WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 8000)  # 0.5s of silence
    return buf.getvalue()


def _mock_process_audio(mocker, **overrides) -> None:
    result = {
        "processed_text": "Hello world.",
        "raw_transcript": "Um hello world.",
        "tone_applied": "neutral",
    }
    result.update(overrides)
    mocker.patch.object(
        audio_route,
        "process_audio",
        mocker.AsyncMock(return_value=result),
    )


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "vocatype-backend"


class TestProcessAudio:
    def test_success(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        _mock_process_audio(mocker)
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Gmail"})},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_text"] == "Hello world."
        assert body["tone_applied"] == "neutral"

    def test_invalid_context_json(self, client: TestClient, wav_bytes: bytes) -> None:
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "not json"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

    def test_missing_audio_file(self, client: TestClient) -> None:
        resp = client.post(
            "/process-audio",
            data={"context": "{}"},
        )
        assert resp.status_code == 422  # FastAPI validation error

    def test_empty_audio_file(self, client: TestClient, mocker) -> None:
        _mock_process_audio(mocker)
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("empty.wav", b"", "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"]

    def test_oversized_audio_returns_413(self, client: TestClient, mocker) -> None:
        mocker.patch.object(
            audio_route,
            "process_audio",
            mocker.AsyncMock(
                side_effect=ValueError("Audio file too large: 21.0MB exceeds maximum of 20MB.")
            ),
        )
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("big.wav", b"\x00" * 1024, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    def test_gemini_unavailable_returns_503(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        mocker.patch.object(
            audio_route,
            "process_audio",
            mocker.AsyncMock(side_effect=RuntimeError("Gemini processing failed: boom")),
        )
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 503
        assert "boom" in resp.json()["detail"]

    def test_unexpected_error_returns_500(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        mocker.patch.object(
            audio_route,
            "process_audio",
            mocker.AsyncMock(side_effect=Exception("unexpected")),
        )
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 500
