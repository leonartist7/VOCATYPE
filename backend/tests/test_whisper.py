"""Unit tests for the local faster-whisper transcription service."""

from __future__ import annotations

import io
import wave

import pytest


def _make_silent_wav_bytes(duration_seconds: float = 0.5) -> bytes:
    """Generate a valid WAV in memory (16 kHz, mono, 16-bit PCM)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * duration_seconds))
    return buf.getvalue()


class FakeSegment:
    def __init__(self, text: str):
        self.text = text


class FakeInfo:
    def __init__(self, language="en", language_probability=0.99, duration=1.0):
        self.language = language
        self.language_probability = language_probability
        self.duration = duration


def _patch_whisper_model(mocker):
    """Replace the global _model with a mock that returns canned segments."""

    fake_model = mocker.MagicMock()
    segments = [FakeSegment("hello"), FakeSegment("world")]
    info = FakeInfo()
    fake_model.transcribe.return_value = (segments, info)

    mocker.patch("app.services.whisper._model", fake_model)
    return fake_model


class TestWhisperService:
    def test_transcribes_wav_bytes(self, mocker):
        _patch_whisper_model(mocker)

        from app.services.whisper import transcribe

        wav = _make_silent_wav_bytes(0.5)
        result = transcribe(wav)

        assert result == "hello world"

    def test_empty_audio_returns_empty_string(self, mocker):
        _patch_whisper_model(mocker)
        mocker.patch("app.services.whisper._model").transcribe.return_value = ([], FakeInfo())

        from app.services.whisper import transcribe

        wav = _make_silent_wav_bytes(0.1)
        result = transcribe(wav, language="en")

        assert result == ""

    def test_singleton_loaded_once(self, mocker):
        """The global _model is only initialised the first time."""
        # Mock the model class so we can count constructor calls without
        # actually downloading anything. The transcribe() path is handled
        # by _patch_whisper_model below, which also sets up a valid return
        # value so the unpacking on line 65 doesn't crash.
        whisper_model_mock = mocker.patch("app.services.whisper.WhisperModel")
        # The mock constructor returns another mock whose .transcribe()
        # returns a valid (segments, info) tuple.
        whisper_model_mock.return_value.transcribe.return_value = (
            [FakeSegment("hi")],
            FakeInfo(),
        )

        import app.services.whisper as svc

        svc._model = None

        svc.transcribe(_make_silent_wav_bytes(0.2))
        svc.transcribe(_make_silent_wav_bytes(0.2))

        assert whisper_model_mock.call_count == 1

    def test_language_hint_is_passed(self, mocker):
        fake = _patch_whisper_model(mocker)

        from app.services.whisper import transcribe

        transcribe(_make_silent_wav_bytes(0.3), language="es")
        _, kwargs = fake.transcribe.call_args
        assert kwargs["language"] == "es"

    def test_auto_language_detection(self, mocker):
        fake = _patch_whisper_model(mocker)

        from app.services.whisper import transcribe

        transcribe(_make_silent_wav_bytes(0.3), language="auto")
        _, kwargs = fake.transcribe.call_args
        assert kwargs["language"] is None


def _make_silent_webm_bytes() -> bytes:
    """Generate a tiny valid webm (Opus audio) in memory via PyAV."""
    import av

    buf = io.BytesIO()
    container = av.open(buf, "w", format="webm")
    stream = container.add_stream("libopus", rate=16000)
    stream.layout = "mono"

    import numpy as np

    frame = av.AudioFrame.from_ndarray(
        np.zeros((1, 1600), dtype=np.int16), format="s16", layout="mono"
    )
    frame.sample_rate = 16000
    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    return buf.getvalue()


class TestWhisperDecode:
    def test_webm_falls_back_to_pyav(self, mocker):
        """Non-WAV containers are decoded via PyAV before transcription."""
        _patch_whisper_model(mocker)

        from app.services.whisper import transcribe

        webm = _make_silent_webm_bytes()
        result = transcribe(webm)
        assert result == "hello world"

    def test_garbage_bytes_raise_value_error(self, mocker):
        _patch_whisper_model(mocker)

        from app.services.whisper import transcribe

        with pytest.raises(ValueError):
            transcribe(b"\x00\x01\x02not-an-audio-file")
