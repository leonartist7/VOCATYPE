"""
HTTP client for communicating with the Vocatype backend.
Sends audio + context via multipart POST, returns processed text.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)

# Reusable client with connection pooling
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Get or create a persistent HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            base_url=config.backend_url,
            timeout=httpx.Timeout(
                connect=5.0,
                read=30.0,  # Gemini processing can take a few seconds
                write=10.0,
                pool=5.0,
            ),
        )
    return _client


def send_audio(
    audio_bytes: bytes,
    context: dict[str, Any],
    max_retries: int = 2,
) -> str | None:
    """
    Send audio and context to the backend for processing.

    Args:
        audio_bytes: WAV file bytes.
        context: Dict with app_name, platform, etc.
        max_retries: Number of retry attempts on transient failures.

    Returns:
        The processed text string, or None if all attempts fail.
    """
    client = _get_client()
    context_json = json.dumps(context)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Sending audio to backend (attempt %d/%d, %d bytes, context=%s)",
                attempt,
                max_retries,
                len(audio_bytes),
                context_json,
            )

            response = client.post(
                "/process-audio",
                files={"audio_file": ("recording.wav", audio_bytes, "audio/wav")},
                data={"context": context_json},
            )

            if response.status_code == 200:
                result = response.json()
                processed = result.get("processed_text", "")
                tone = result.get("tone_applied", "unknown")
                logger.info(
                    "✅ Received processed text (%d chars, tone=%s): %s",
                    len(processed),
                    tone,
                    processed[:80],
                )
                return processed

            # Non-200 response
            logger.error(
                "Backend returned %d: %s",
                response.status_code,
                response.text[:200],
            )

            # Don't retry on client errors (4xx)
            if 400 <= response.status_code < 500:
                logger.error("Client error — not retrying.")
                return None

        except httpx.ConnectError as e:
            logger.error("Connection error (attempt %d): %s", attempt, e)
        except httpx.TimeoutException as e:
            logger.error("Timeout (attempt %d): %s", attempt, e)
        except Exception as e:
            logger.error("Unexpected error (attempt %d): %s", attempt, e, exc_info=True)

    logger.error("All %d attempts failed. No text returned.", max_retries)
    return None


def close_client() -> None:
    """Close the HTTP client. Call on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
        _client = None
        logger.info("HTTP client closed.")
