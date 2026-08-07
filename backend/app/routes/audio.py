"""
Audio processing endpoint.
Accepts multipart audio + JSON context, returns AI-processed text.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.schemas import AudioContext, ErrorResponse, ProcessedResponse
from app.services.gemini import process_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audio"])


@router.post(
    "/process-audio",
    response_model=ProcessedResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        413: {"model": ErrorResponse, "description": "Audio file too large"},        500: {"model": ErrorResponse, "description": "Processing error"},
        503: {"model": ErrorResponse, "description": "Gemini service unavailable"},
    },
    summary="Process dictated audio through Gemini AI",
    description=(
        "Upload an audio file and a JSON context string. "
        "Gemini transcribes the audio, strips filler words, adapts tone to the "
        "active app, and returns clean formatted text."
    ),
)
async def process_audio_endpoint(
    audio_file: Annotated[
        UploadFile,
        File(description="Audio file (.wav, .m4a, .webm, .ogg, .mp3, .flac, .aac, .3gp)"),
    ],
    context: Annotated[
        str,
        Form(description="JSON string with keys: app_name, platform, selected_text, language"),
    ] = "{}",
) -> ProcessedResponse:
    """
    Process an audio recording through the Gemini AI pipeline.

    1. Validate and parse the context JSON.
    2. Read the uploaded audio file.
    3. Send audio + context to Gemini for transcription and processing.
    4. Return the cleaned, formatted text.
    """

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
        "Received audio: filename=%s, size=%d bytes, context=%s",
        audio_file.filename,
        len(audio_bytes),
        audio_context.model_dump_json(),
    )

    # ── Process through Gemini ──────────────────────────────────────────────
    try:
        result = await process_audio(
            audio_bytes=audio_bytes,
            filename=audio_file.filename or "audio.wav",
            content_type=audio_file.content_type,
            context=audio_context.model_dump(),
        )
    except ValueError as e:
        # File too large or invalid format
        logger.warning("Audio validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        logger.error("Gemini processing error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Unexpected error processing audio: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {e}",
        ) from e

    return ProcessedResponse(**result)
