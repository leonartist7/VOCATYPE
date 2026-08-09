"""
Audio processing endpoint.
Accepts multipart audio + JSON context, returns AI-processed text.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.models.schemas import AudioContext, ErrorResponse, ProcessedResponse
from app.services.gemini import process_audio
from app.services.metrics import (
    AUDIO_BYTES,
    PROCESS_AUDIO_DURATION,
    PROCESS_AUDIO_TOTAL,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audio"])


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
        "Upload an audio file and a JSON context string. "
        "If the backend is configured with `TRANSCRIPTION_ENGINE=whisper`, "
        "audio is transcribed locally via faster-whisper (offline). "
        "Otherwise the audio is sent to Gemini for transcription + tone adaptation."
    ),
)
async def process_audio_endpoint(
    audio_file: Annotated[
        UploadFile,
        File(description="Audio file (.wav, .m4a, .webm, .ogg, .mp3, .flac, .aac, .3gp)"),
    ],
    context: Annotated[
        str, Form(description="JSON string with keys: app_name, platform, selected_text, language")
    ] = "{}",
) -> ProcessedResponse:
    """
    Process an audio recording.

    In **Gemini mode** (default): transcribes via Gemini, strips filler
    words, adapts tone based on the active app, and returns clean formatted text.

    In **Whisper mode** (`TRANSCRIPTION_ENGINE=whisper`): transcribes locally
    with faster-whisper — works fully offline. No tone adaptation or filler
    removal is applied (the raw transcription is returned as both
    `processed_text` and `raw_transcript`).
    """
    settings = get_settings()
    engine = settings.transcription_engine

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
        "Received audio: engine=%s filename=%s size=%d bytes context=%s",
        engine,
        audio_file.filename,
        len(audio_bytes),
        audio_context.model_dump_json(),
    )

    AUDIO_BYTES.observe(len(audio_bytes))

    # ── Dispatch to engine ──────────────────────────────────────────────────
    try:
        with PROCESS_AUDIO_DURATION.time():
            if engine == "whisper":
                result = _process_whisper(audio_bytes, audio_context)
            else:
                result = await process_audio(
                    audio_bytes=audio_bytes,
                    filename=audio_file.filename or "audio.wav",
                    content_type=audio_file.content_type,
                    context=audio_context.model_dump(),
                )
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


def _process_whisper(audio_bytes: bytes, context: AudioContext) -> dict[str, str]:
    """Transcribe locally with faster-whisper and return a Gemini-compatible dict."""
    from app.services.whisper import transcribe as whisper_transcribe

    language = context.language or "en"

    transcript = whisper_transcribe(audio_bytes, language=language)

    return {
        "processed_text": transcript,
        "raw_transcript": transcript,
        "tone_applied": "none",
    }
