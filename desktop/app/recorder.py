"""
Microphone audio recorder using PyAudio.
Records PCM audio into an in-memory WAV buffer while a hotkey is held.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
import threading
import wave
from typing import Any

from app.config import config

logger = logging.getLogger(__name__)


class AudioRecorder:
    """
    Thread-safe audio recorder that captures microphone input to a WAV buffer.

    Usage:
        recorder = AudioRecorder()
        recorder.start_recording()
        # ... user speaks ...
        wav_bytes = recorder.stop_recording()
    """

    def __init__(self) -> None:
        self._pyaudio: Any = None
        self._pa: Any | None = None
        self._stream: Any | None = None
        self._frames: list[bytes] = []
        self._is_recording = False
        self._lock = threading.Lock()

    def _ensure_pyaudio(self) -> Any:
        """Lazily initialize PyAudio.

        PyAudio is imported lazily so the app (and its test suite) can start
        even when the native PortAudio dependency is unavailable on a given
        platform / Python version.
        """
        if self._pa is None:
            pyaudio = importlib.import_module("pyaudio")
            self._pyaudio = pyaudio
            self._pa = pyaudio.PyAudio()
        return self._pa

    def start_recording(self) -> None:
        """Start capturing microphone audio."""
        with self._lock:
            if self._is_recording:
                logger.warning("Already recording — ignoring start request.")
                return

            self._frames = []
            pa = self._ensure_pyaudio()
            pyaudio = self._pyaudio

            try:
                self._stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=config.channels,
                    rate=config.sample_rate,
                    input=True,
                    frames_per_buffer=config.chunk_size,
                    stream_callback=self._audio_callback,
                )
                self._stream.start_stream()
                self._is_recording = True
                logger.info(
                    "🎙️  Recording started (rate=%d, channels=%d)",
                    config.sample_rate,
                    config.channels,
                )
            except Exception as e:
                logger.error("Failed to start recording: %s", e)
                self._cleanup_stream()
                raise

    def stop_recording(self) -> bytes | None:
        """
        Stop recording and return the captured audio as WAV bytes.

        Returns:
            WAV file bytes, or None if no audio was captured.
        """
        with self._lock:
            if not self._is_recording:
                logger.warning("Not recording — ignoring stop request.")
                return None

            self._is_recording = False
            self._cleanup_stream()

            if not self._frames:
                logger.warning("No audio frames captured.")
                return None

            wav_bytes = self._frames_to_wav()
            frame_count = len(self._frames)
            duration = (frame_count * config.chunk_size) / config.sample_rate
            logger.info(
                "🛑 Recording stopped: %d frames, ~%.1fs, %d bytes WAV",
                frame_count,
                duration,
                len(wav_bytes),
            )
            self._frames = []
            return wav_bytes

    def _audio_callback(
        self,
        in_data: bytes | None,
        frame_count: int,
        time_info: dict,
        status_flags: int,
    ) -> tuple[None, int]:
        """PyAudio callback — accumulates audio frames."""
        if in_data and self._is_recording:
            self._frames.append(in_data)
        return (None, self._pyaudio.paContinue)

    def _frames_to_wav(self) -> bytes:
        """Convert accumulated PCM frames to a WAV file in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(config.channels)
            wf.setsampwidth(config.sample_width)
            wf.setframerate(config.sample_rate)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()

    def _cleanup_stream(self) -> None:
        """Safely close the audio stream."""
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                logger.debug("Stream cleanup error (non-fatal): %s", e)
            finally:
                self._stream = None

    def cleanup(self) -> None:
        """Release all PyAudio resources. Call on shutdown."""
        with self._lock:
            self._cleanup_stream()
            if self._pa is not None:
                with contextlib.suppress(Exception):
                    self._pa.terminate()
                self._pa = None
            logger.info("AudioRecorder resources released.")
