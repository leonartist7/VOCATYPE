"""
Microphone audio recorder using sounddevice.

Records PCM audio into an in-memory WAV buffer while a hotkey is held.

`sounddevice` bundles its own PortAudio binaries, so it installs cleanly on
modern Python versions (including 3.13+) where the PyAudio package provides
no binary wheels.
"""

from __future__ import annotations

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
        self._sounddevice: Any = None
        self._stream: Any | None = None
        self._frames: list[bytes] = []
        self._is_recording = False
        self._lock = threading.Lock()

    def _ensure_sounddevice(self) -> Any:
        """Lazily import sounddevice.

        The import is deferred so the app (and its test suite) can start even
        when the native PortAudio dependency is unavailable on a given
        platform / Python version.
        """
        if self._sounddevice is None:
            self._sounddevice = importlib.import_module("sounddevice")
        return self._sounddevice

    def start_recording(self) -> None:
        """Start capturing microphone audio."""
        with self._lock:
            if self._is_recording:
                logger.warning("Already recording — ignoring start request.")
                return

            self._frames = []
            sd = self._ensure_sounddevice()

            try:
                self._stream = sd.RawInputStream(
                    samplerate=config.sample_rate,
                    channels=config.channels,
                    dtype="int16",  # matches sample_width = 2
                    blocksize=config.chunk_size,
                    callback=self._audio_callback,
                )
                self._stream.start()
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
        indata: bytes | Any,
        frames: int,
        time_info: dict,
        status_flags: int,
    ) -> None:
        """sounddevice RawInputStream callback — accumulates raw PCM frames."""
        if indata and self._is_recording:
            self._frames.append(bytes(indata))
        if status_flags:
            logger.debug("Audio callback status: %s", status_flags)

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
                if self._stream.active:
                    self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug("Stream cleanup error (non-fatal): %s", e)
            finally:
                self._stream = None

    def cleanup(self) -> None:
        """Release all audio resources. Call on shutdown."""
        with self._lock:
            self._cleanup_stream()
            logger.info("AudioRecorder resources released.")
