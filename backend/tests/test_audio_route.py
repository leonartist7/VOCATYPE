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
from app.middleware import _rate_buckets
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
        assert body["engine"] == "gemini"
        assert body["model"] == "gemini-flash-latest"


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


class TestAuthentication:
    @staticmethod
    def _patch_token(mocker, token: str) -> None:
        from app.config import Settings

        settings = Settings(gemini_api_key="test", api_token=token)
        mocker.patch("app.middleware.get_settings", return_value=settings)

    def test_no_token_configured_accepts_requests(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        _mock_process_audio(mocker)
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 200

    def test_missing_token_rejected(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        self._patch_token(mocker, "sekrit")
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 401

    def test_wrong_token_rejected(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        self._patch_token(mocker, "sekrit")
        resp = client.post(
            "/process-audio",
            headers={"X-API-Token": "wrong"},
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 401

    def test_correct_token_accepted(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        self._patch_token(mocker, "sekrit")
        _mock_process_audio(mocker)
        resp = client.post(
            "/process-audio",
            headers={"X-API-Token": "sekrit"},
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 200

    def test_health_always_public(self, client: TestClient, mocker) -> None:
        self._patch_token(mocker, "sekrit")
        resp = client.get("/health")
        assert resp.status_code == 200


class TestRateLimiting:
    def test_rate_limit_exceeded_returns_429(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        _rate_buckets.clear()
        from app.config import Settings

        settings = Settings(gemini_api_key="test", rate_limit_per_minute=2)
        mocker.patch("app.middleware.get_settings", return_value=settings)
        _mock_process_audio(mocker)

        for _ in range(2):
            resp = client.post(
                "/process-audio",
                files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
                data={"context": "{}"},
            )
            assert resp.status_code == 200

        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 429
        _rate_buckets.clear()


class TestMetricsEndpoint:
    def test_metrics_endpoint_returns_prometheus_format(self, client: TestClient) -> None:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]


class TestWhisperEngine:
    @staticmethod
    def _patch_engine(mocker, engine: str):
        from app.config import Settings

        ws = Settings(
            transcription_engine=engine,
            gemini_api_key="test",
            whisper_model="tiny.en",
        )
        mocker.patch("app.routes.audio.get_settings", return_value=ws)

    def test_whisper_engine_returns_raw_transcript(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        self._patch_engine(mocker, "whisper")
        mocker.patch("app.services.whisper.transcribe", return_value="hello world")

        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Test"})},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_text"] == "hello world"
        assert body["raw_transcript"] == "hello world"
        assert body["tone_applied"] == "none"

    def test_whisper_engine_with_language(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        self._patch_engine(mocker, "whisper")
        mock_transcribe = mocker.patch("app.services.whisper.transcribe", return_value="hola mundo")

        client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Test", "language": "es"})},
        )
        mock_transcribe.assert_called_once()
        assert mock_transcribe.call_args[1]["language"] == "es"

    def test_whisper_engine_default_gemini_still_works(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        """gemini engine should still be the default path."""
        _mock_process_audio(mocker)
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tone_applied"] == "neutral"
