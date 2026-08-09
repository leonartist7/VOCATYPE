"""
DeepSeek integration — cheap online text cleaning of whisper transcripts.

DeepSeek V4 Flash is a text-only LLM (no audio support), so this service takes
a raw speech-to-text transcript and returns a cleaned version: punctuation,
filler-word removal, grammar fixes, and app-appropriate tone.

Uses the OpenAI-compatible chat completions API via httpx (no extra SDK).

Pricing reference (2026): deepseek-v4-flash = $0.14/1M input tokens,
$0.28/1M output tokens — a few cents per million dictations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.services.prompts import build_system_prompt, determine_tone

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def initialize_deepseek() -> None:
    """Configure the shared async HTTP client. Called once at startup."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={"Authorization": f"Bearer {get_settings().deepseek_api_key}"},
        )
        logger.info("DeepSeek client initialized with model: %s", get_settings().deepseek_model)


async def clean_transcript(transcript: str, context: dict[str, Any]) -> dict[str, str]:
    """
    Send a raw transcript to DeepSeek for cleaning and return processed text.

    Args:
        transcript: Raw speech-to-text output (e.g. from faster-whisper).
        context: Client context dict (app_name, platform, selected_text, language).

    Returns:
        Dict with keys: processed_text, tone_applied.

    Raises:
        RuntimeError: If the DeepSeek API call fails.
    """
    global _client
    settings = get_settings()

    if _client is None or _client.is_closed:
        initialize_deepseek()

    if not settings.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured — online mode requires a DeepSeek API key."
        )

    system_prompt = build_system_prompt(context)
    tone = determine_tone(context.get("app_name", "unknown"))

    payload: dict[str, Any] = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": 0.1,  # Low temp for accurate cleaning
        "thinking": {"type": "disabled"},  # Avoid paying for reasoning tokens
        "stream": False,
    }

    try:
        resp = await _client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("DeepSeek API error: %s", e, exc_info=True)
        raise RuntimeError(f"DeepSeek cleaning failed: {e}") from e

    try:
        raw_text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        logger.error("Unexpected DeepSeek response shape: %s", data)
        raise RuntimeError(f"DeepSeek returned an unexpected response: {e}") from e

    logger.debug("DeepSeek raw response: %s", raw_text[:200])

    return _parse_deepseek_response(raw_text, tone)


def _parse_deepseek_response(raw_text: str, tone: str) -> dict[str, str]:
    """
    Parse the DeepSeek response, handling both JSON and plain text responses.

    Returns:
        Dict with processed_text (and raw_transcript passthrough is handled by caller).
    """
    # Strip markdown code fences if the model wraps in ```json ... ```
    cleaned = raw_text
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        return {"processed_text": parsed.get("processed_text", cleaned), "tone_applied": tone}
    except json.JSONDecodeError:
        logger.warning("DeepSeek returned non-JSON response. Using as plain text.")
        return {"processed_text": cleaned, "tone_applied": tone}
