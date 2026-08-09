"""
Local offline transcription via faster-whisper (CTranslate2).

Uses a lazily-loaded, module-level singleton so the model is shared across
requests. The first transcription call downloads the model from HuggingFace
(~39 MB for "tiny.en") and caches it locally; subsequent calls are instant.
"""

from __future__ import annotations

import io
import logging
import wave

import numpy as np
from faster_whisper import WhisperModel

from app.config import get_settings

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def _load_model() -> WhisperModel:
    """Return a warmed WhisperModel singleton."""
    global _model
    if _model is None:
        settings = get_settings()
        logger.info(
            "Loading faster-whisper model=%s device=%s compute=%s …",
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            cpu_threads=4,
            num_workers=1,
        )
        logger.info("Whisper model ready ✅")
    return _model


def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """
    Transcribe raw WAV audio bytes to text using the local whisper model.

    Args:
        audio_bytes: Raw WAV file bytes (16 kHz, mono, 16-bit PCM).
        language: ISO 639-1 language code hint (default "en").

    Returns:
        Transcription text with no punctuation / filler-word processing.
    """
    with io.BytesIO(audio_bytes) as buf, wave.open(buf, "rb") as wf:
        frames = wf.readframes(wf.getnframes())

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    model = _load_model()
    segments, info = model.transcribe(
        audio,
        language=None if language == "auto" else language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments_list = list(segments)
    if not segments_list:
        logger.warning("Whisper returned no segments.")
        return ""

    text = " ".join(seg.text.strip() for seg in segments_list)

    logger.info(
        "Whisper transcription: %d segments, %.1fs audio, detected=%.2f %% %s",
        len(segments_list),
        info.duration,
        info.language_probability * 100,
        info.language,
    )
    return text
