"""
Audio processing endpoint.
Accepts multipart audio + JSON context, returns AI-processed text.

Pipeline:
  1. faster-whisper transcribes the audio locally (works fully offline).
  2. In online mode the raw transcript is sent to DeepSeek V4 Flash for
     cleaning (punctuation, filler words, tone) — a few cents per million.
  3. In offline mode the raw whisper transcript is returned as-is.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from app.config import get_settings
from app.models.schemas import AudioContext, ErrorResponse, ProcessedResponse
from app.services.deepseek import clean_transcript
from app.services.metrics import (
    AUDIO_BYTES,
    PROCESS_AUDIO_DURATION,
    PROCESS_AUDIO_TOTAL,
)
from app.services.whisper import transcribe as whisper_transcribe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audio"])


def _resolve_mode(settings, override: str | None) -> str:
    """Resolve the effective transcription mode.

    The client may override the configured mode per-request via the
    X-Transcription-Mode header ("offline" or "online"). This lets the
    preview UI offer a live offline/online toggle.
    """
    if override and override.lower() in {"offline", "online"}:
        return override.lower()
    return "offline" if not settings.is_online else "online"


@router.post(
    "/process-audio",
    response_model=ProcessedResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        413: {"model": ErrorResponse, "description": "Audio file too large"},
        500: {"model": ErrorResponse, "description": "Processing error"},
        503: {"model": ErrorResponse, "description": "Transcription service unavailable"},
    },
    summary="Process dictated audio",
    description=(
        "Transcribes audio locally with faster-whisper, then — in online mode — "
        "cleans the text with DeepSeek V4 Flash (punctuation, fillers, tone). "
        "Set X-Transcription-Mode to 'offline' or 'online' to override per request."
    ),
)
async def process_audio_endpoint(
    audio_file: Annotated[
        UploadFile,
        File(description="Audio file (.wav, .webm, .ogg, .mp3, .m4a, .flac, .aac, .3gp)"),
    ],
    context: Annotated[
        str, Form(description="JSON string with keys: app_name, platform, selected_text, language")
    ] = "{}",
    x_transcription_mode: Annotated[str | None, Header(alias="X-Transcription-Mode")] = None,
) -> ProcessedResponse:
    """
    Process an audio recording.

    **Offline mode** (default config): local faster-whisper transcription,
    fully offline. Returns the raw transcript (no punctuation cleaning).

    **Online mode**: same local transcription, then DeepSeek V4 Flash adds
    punctuation, strips filler words, fixes grammar, and applies tone based
    on the active app.
    """
    settings = get_settings()
    mode = _resolve_mode(settings, x_transcription_mode)

    # ── Parse context ───────────────────────────────────────────────────────
    try:
        context_dict = json.loads(context)
        audio_context = AudioContext(**context_dict)
    except json.JSONDecodeError as e:
        logger.warning("Invalid context JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in 'context' field: {e}",
        ) from e
    except Exception as e:
        logger.warning("Context validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Context validation error: {e}",
        ) from e

    # ── Read audio file ─────────────────────────────────────────────────────
    try:
        audio_bytes = await audio_file.read()
    except Exception as e:
        logger.error("Failed to read audio file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read audio file: {e}",
        ) from e

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    logger.info(
        "Received audio: mode=%s filename=%s size=%d bytes context=%s",
        mode,
        audio_file.filename,
        len(audio_bytes),
        audio_context.model_dump_json(),
    )

    AUDIO_BYTES.observe(len(audio_bytes))

    # ── Process ─────────────────────────────────────────────────────────────
    try:
        with PROCESS_AUDIO_DURATION.time():
            result = await _process(mode, audio_bytes, audio_context)
    except ValueError as e:
        PROCESS_AUDIO_TOTAL.labels(outcome="error").inc()
        logger.warning("Audio validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        PROCESS_AUDIO_TOTAL.labels(outcome="error").inc()
        logger.error("Processing error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except Exception as e:
        PROCESS_AUDIO_TOTAL.labels(outcome="error").inc()
        logger.error("Unexpected error processing audio: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {e}",
        ) from e

    PROCESS_AUDIO_TOTAL.labels(outcome="success").inc()
    return ProcessedResponse(**result)


async def _process(mode: str, audio_bytes: bytes, audio_context: AudioContext) -> dict[str, str]:
    """Run the transcription pipeline for the given mode."""
    language = audio_context.language or "en"

    # Always transcribe locally — whisper is the STT engine in both modes.
    transcript = whisper_transcribe(audio_bytes, language=language)

    if mode == "online":
        result = await clean_transcript(transcript, audio_context.model_dump())
        result["raw_transcript"] = transcript
        return result

    # Offline: raw transcript, no LLM cleaning.
    return {
        "processed_text": transcript,
        "raw_transcript": transcript,
        "tone_applied": "none",
    }
