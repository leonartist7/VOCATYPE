"""Unit tests for the desktop audio recorder (sounddevice stubbed)."""

from __future__ import annotations

import io
import wave

from app.config import config
from app.recorder import AudioRecorder


class TestAudioRecorder:
    def test_stream_configured_from_config(self) -> None:
        """RawInputStream must be opened with the configured audio params."""
        import sounddevice

        rec = AudioRecorder()
        rec.start_recording()

        opened = sounddevice.last_open
        assert opened["samplerate"] == config.sample_rate
        assert opened["channels"] == config.channels
        assert opened["dtype"] == "int16"
        assert opened["blocksize"] == config.chunk_size
        assert opened["callback"].__self__ is rec
        assert opened["callback"].__func__ is AudioRecorder._audio_callback
        assert rec._stream.active is True

        rec.cleanup()

    def test_start_and_stop_recording_produces_wav(self) -> None:
        rec = AudioRecorder()
        rec.start_recording()
        # Simulate a callback delivering PCM frames
        rec._audio_callback(b"\x00\x00" * 400, 400, {}, 0)
        rec._audio_callback(b"\x00\x00" * 400, 400, {}, 0)

        wav_bytes = rec.stop_recording()
        assert wav_bytes is not None
        assert len(wav_bytes) > 44  # WAV header + data

        # Validate it is a readable WAV file

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 800

        rec.cleanup()

    def test_stop_without_start_returns_none(self) -> None:
        rec = AudioRecorder()
        assert rec.stop_recording() is None

    def test_double_start_ignored(self) -> None:
        rec = AudioRecorder()
        rec.start_recording()
        rec.start_recording()  # should not raise or crash
        rec._audio_callback(b"\x00\x00" * 400, 400, {}, 0)
        wav_bytes = rec.stop_recording()
        assert wav_bytes is not None
        rec.cleanup()

    def test_no_frames_returns_none(self) -> None:
        rec = AudioRecorder()
        rec.start_recording()
        assert rec.stop_recording() is None
        rec.cleanup()

    def test_cleanup_releases_resources(self) -> None:
        rec = AudioRecorder()
        rec.start_recording()
        rec.cleanup()
        assert rec._sounddevice is not None
        assert rec._stream is None
