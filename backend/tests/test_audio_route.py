"""Integration tests for the /process-audio and /health endpoints.

Uses FastAPI's TestClient with whisper and DeepSeek services mocked.
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


def _mock_whisper(mocker, transcript: str = "hello world") -> None:
    mocker.patch("app.routes.audio.whisper_transcribe", return_value=transcript)


def _mock_deepseek(mocker, **overrides):
    result = {"processed_text": "Hello world.", "tone_applied": "neutral"}
    result.update(overrides)
    return mocker.patch("app.routes.audio.clean_transcript", mocker.AsyncMock(return_value=result))


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "vocatype-backend"
        assert body["mode"] == "online"
        assert body["whisper_model"] == "tiny.en"
        assert body["cleaner"] == "deepseek-v4-flash"


class TestProcessAudio:
    def test_online_mode_success(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        _mock_whisper(mocker)
        _mock_deepseek(mocker)
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Gmail"})},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_text"] == "Hello world."
        assert body["raw_transcript"] == "hello world"
        assert body["tone_applied"] == "neutral"
        assert body["cleaning_error"] is None

    def test_offline_mode_returns_raw(self, client: TestClient, wav_bytes: bytes, mocker) -> None:
        _mock_whisper(mocker, transcript="um hello there um")
        resp = client.post(
            "/process-audio",
            headers={"X-Transcription-Mode": "offline"},
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Gmail"})},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_text"] == "um hello there um"
        assert body["raw_transcript"] == "um hello there um"
        assert body["tone_applied"] == "none"
        assert body["cleaning_error"] is None

    def test_online_override_runs_deepseek(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        _mock_whisper(mocker, transcript="um hello")
        deepseek = _mock_deepseek(mocker)
        client.post(
            "/process-audio",
            headers={"X-Transcription-Mode": "online"},
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": json.dumps({"app_name": "Gmail"})},
        )
        deepseek.assert_called_once()
        assert deepseek.call_args[0][1]["app_name"] == "Gmail"

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
        _mock_whisper(mocker)
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
            "whisper_transcribe",
            side_effect=ValueError("Audio file too large: 21.0MB exceeds maximum of 20MB."),
        )
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("big.wav", b"\x00" * 1024, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    def test_deepseek_unavailable_degrades_to_raw(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        """When DeepSeek cleaning fails, dictation must still return the transcript."""
        _mock_whisper(mocker, transcript="hello there")
        mocker.patch.object(
            audio_route,
            "clean_transcript",
            mocker.AsyncMock(side_effect=RuntimeError("DeepSeek cleaning failed: boom")),
        )
        resp = client.post(
            "/process-audio",
            files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
            data={"context": "{}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed_text"] == "hello there"
        assert body["raw_transcript"] == "hello there"
        assert body["tone_applied"] == "none"
        assert "boom" in body["cleaning_error"]

    def test_unexpected_error_returns_500(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        _mock_whisper(mocker)
        mocker.patch.object(
            audio_route,
            "clean_transcript",
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

        settings = Settings(deepseek_api_key="test", api_token=token)
        mocker.patch("app.middleware.get_settings", return_value=settings)

    def test_no_token_configured_accepts_requests(
        self, client: TestClient, wav_bytes: bytes, mocker
    ) -> None:
        _mock_whisper(mocker)
        _mock_deepseek(mocker)
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
        _mock_whisper(mocker)
        _mock_deepseek(mocker)
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

        settings = Settings(deepseek_api_key="test", rate_limit_per_minute=2)
        mocker.patch("app.middleware.get_settings", return_value=settings)
        _mock_whisper(mocker)
        _mock_deepseek(mocker)

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
