"""Unit tests for the desktop audio recorder (PyAudio stubbed)."""

from __future__ import annotations

import wave

from app.recorder import AudioRecorder


class TestAudioRecorder:
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
        import io

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
        assert rec._pa is None
        assert rec._stream is None
