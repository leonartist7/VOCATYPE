"""
Local offline transcription via faster-whisper (CTranslate2).

Uses a lazily-loaded, module-level singleton so the model is shared across
requests. The first transcription call downloads the model from HuggingFace
(~39 MB for "tiny.en") and caches it locally; subsequent calls are instant.

Decodes both WAV (stdlib) and compressed audio like webm/ogg/mp3 via PyAV,
so browser recordings work out of the box.
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


def _decode_audio(audio_bytes: bytes) -> np.ndarray:
    """
    Decode audio bytes to a float32 numpy array at 16 kHz mono.

    Fast path: WAV via the stdlib. Fallback: any container PyAV supports
    (webm, ogg, mp3, m4a) resampled to 16 kHz mono.
    """
    # ── Fast path: WAV ──
    try:
        with io.BytesIO(audio_bytes) as buf, wave.open(buf, "rb") as wf:
            if wf.getframerate() == 16000 and wf.getnchannels() == 1:
                frames = wf.readframes(wf.getnframes())
                return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    except wave.Error:
        pass  # Not a WAV — fall through to PyAV

    # ── Fallback: PyAV (webm/ogg/mp3/etc.) ──
    import av
    import av.audio.resampler

    container = av.open(io.BytesIO(audio_bytes))
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        raise ValueError("No audio stream found in uploaded file.")

    resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=16000)
    chunks: list[np.ndarray] = []
    for frame in container.decode(stream):
        for out_frame in resampler.resample(frame):
            arr = out_frame.to_ndarray()
            chunks.append(arr.reshape(-1))

    # Flush any remaining buffered frames by resampling with no input.
    for out_frame in resampler.resample(None):
        arr = out_frame.to_ndarray()
        chunks.append(arr.reshape(-1))

    if not chunks:
        raise ValueError("No audio frames could be decoded from the uploaded file.")

    return np.concatenate(chunks).astype(np.float32)


def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """
    Transcribe audio bytes to text using the local whisper model.

    Args:
        audio_bytes: Raw audio file bytes (WAV, webm, ogg, mp3, …).
        language: ISO 639-1 language code hint (default "en"). Use "auto"
            for automatic language detection.

    Returns:
        Transcription text with no punctuation / filler-word processing.
    """
    audio = _decode_audio(audio_bytes)

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
