"""
Gemini Flash integration — dynamic prompt construction and audio processing.

This module builds a context-aware system prompt, sends audio + prompt to Gemini
via the official `google-genai` SDK, and parses the structured response.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.transcription import detect_mime_type, validate_audio_size

logger = logging.getLogger(__name__)

# ── App-to-tone mapping ────────────────────────────────────────────────────────

CASUAL_APPS: set[str] = {
    "com.whatsapp",
    "com.facebook.orca",  # Messenger
    "com.snapchat.android",
    "com.instagram.android",
    "org.telegram.messenger",
    "com.discord",
    "com.twitter.android",
    "com.reddit.frontpage",
    "com.viber.voip",
    "com.tencent.mm",  # WeChat
    "com.zhiliaoapp.musically",  # TikTok
    # Desktop window title fragments
    "whatsapp",
    "messenger",
    "telegram",
    "discord",
    "slack",
    "signal",
    "imessage",
    "messages",
}

PROFESSIONAL_APPS: set[str] = {
    "com.google.android.gm",  # Gmail
    "com.microsoft.office.outlook",
    "com.linkedin.android",
    "com.google.android.apps.docs",
    "com.google.android.apps.docs.editors.docs",
    "com.google.android.apps.docs.editors.sheets",
    "com.microsoft.office.word",
    "com.microsoft.office.excel",
    "com.notion.id",
    # Desktop window title fragments
    "gmail",
    "outlook",
    "word",
    "excel",
    "google docs",
    "notion",
    "linkedin",
    "jira",
    "confluence",
    "asana",
}


def _determine_tone(app_name: str) -> str:
    """Determine the appropriate tone based on the active app."""
    app_lower = app_name.lower().strip()

    for casual_id in CASUAL_APPS:
        if casual_id in app_lower:
            return "casual"

    for prof_id in PROFESSIONAL_APPS:
        if prof_id in app_lower:
            return "professional"

    return "neutral"


# ── System Prompt Builder ──────────────────────────────────────────────────────

_BASE_INSTRUCTIONS = """You are Vocatype, an AI dictation engine. Your job is to take spoken audio and convert it into clean, properly formatted text.

CORE RULES — ALWAYS FOLLOW:
1. **Strip filler words**: Remove all "um", "uh", "er", "ah", "like" (when used as filler), "you know", "I mean", "basically", "actually" (when filler), "sort of", "kind of" (when filler), repeated words, false starts, and hesitations.
2. **Fix grammar**: Correct subject-verb agreement, tense consistency, and punctuation. Add proper capitalization.
3. **Preserve intent**: Never change the meaning of what the user said. Only clean up delivery.
4. **Auto-format**: If the user dictates a list (e.g., "first... second... third..." or "number one... number two..."), format it as a properly structured list with bullet points or numbers.
5. **Paragraph breaks**: Insert paragraph breaks at natural topic transitions.
6. **No meta-commentary**: Output ONLY the processed text. Never say "Here's the cleaned text:" or add any explanation.

RESPONSE FORMAT:
You MUST respond with valid JSON only. No markdown, no code fences, no extra text.
{
  "processed_text": "The final cleaned text",
  "raw_transcript": "The raw word-for-word transcription before cleaning"
}"""

_TONE_CASUAL = """
TONE: CASUAL
- Use contractions (don't, can't, won't, it's).
- Keep sentences short and punchy.
- Emoji are acceptable if tone warrants it.
- Informal greetings are fine (hey, hi, what's up).
- Do NOT make the text sound robotic or overly formal."""

_TONE_PROFESSIONAL = """
TONE: PROFESSIONAL
- Use complete, well-structured sentences.
- Avoid contractions when possible.
- Use formal greetings (Dear, Hello, Good morning).
- Maintain a polished, business-appropriate register.
- Structure longer dictations with clear paragraph breaks."""

_TONE_NEUTRAL = """
TONE: NEUTRAL
- Use natural, clear language.
- Balance between casual and formal.
- Contractions are acceptable but not required.
- Focus on clarity and readability."""

_SPEAK_TO_EDIT_INSTRUCTIONS = """
SPEAK-TO-EDIT MODE:
The user has selected existing text and is now speaking a COMMAND about that text.
The selected text is provided below. Treat the spoken audio as an instruction to TRANSFORM
the selected text (e.g., "translate this to Spanish", "make this more formal",
"summarize this", "fix the grammar", "rewrite this as bullet points").

Apply the spoken command to the selected text and return the result.
If the command is unclear, do your best interpretation.

SELECTED TEXT:
\"\"\"
{selected_text}
\"\"\"
"""


def build_system_prompt(context: dict[str, Any]) -> str:
    """
    Construct a dynamic system prompt based on the request context.

    Args:
        context: Dict with keys: app_name, platform, selected_text, language.

    Returns:
        Complete system prompt string.
    """
    parts: list[str] = [_BASE_INSTRUCTIONS]

    # ── Tone layer ──
    app_name = context.get("app_name", "unknown")
    tone = _determine_tone(app_name)

    if tone == "casual":
        parts.append(_TONE_CASUAL)
    elif tone == "professional":
        parts.append(_TONE_PROFESSIONAL)
    else:
        parts.append(_TONE_NEUTRAL)

    # ── Speak-to-edit layer ──
    selected_text = context.get("selected_text")
    if selected_text and selected_text.strip():
        parts.append(_SPEAK_TO_EDIT_INSTRUCTIONS.format(selected_text=selected_text.strip()))

    # ── Language hint ──
    language = context.get("language", "en")
    if language and language != "en":
        parts.append(
            f"\nLANGUAGE: The user is speaking in '{language}'. "
            f"Transcribe and process in that language unless the command says otherwise."
        )

    prompt = "\n\n".join(parts)
    logger.debug(
        "Built system prompt (%d chars) for app='%s', tone='%s'", len(prompt), app_name, tone
    )
    return prompt


# ── Gemini Client ──────────────────────────────────────────────────────────────

_client: genai.Client | None = None


def initialize_gemini() -> None:
    """Configure the Gemini SDK and create the client. Called once at startup."""
    global _client
    settings = get_settings()
    _client = genai.Client(api_key=settings.gemini_api_key)
    logger.info("Gemini client initialized with model: %s", settings.gemini_model)


async def process_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: str | None,
    context: dict[str, Any],
) -> dict[str, str]:
    """
    Send audio + dynamic prompt to Gemini and return processed text.

    Args:
        audio_bytes: Raw audio file bytes.
        filename: Original filename for MIME detection.
        content_type: MIME type from upload header.
        context: Client context dict (app_name, platform, selected_text, language).

    Returns:
        Dict with keys: processed_text, raw_transcript, tone_applied.

    Raises:
        RuntimeError: If Gemini is not initialized or returns an unparseable response.
        ValueError: If audio is too large.
    """
    if _client is None:
        raise RuntimeError("Gemini client not initialized. Call initialize_gemini() first.")

    # Validate audio size
    validate_audio_size(audio_bytes)

    # Detect MIME type
    mime_type = detect_mime_type(filename, content_type)
    logger.info(
        "Processing audio: filename=%s, mime=%s, size=%.1fKB, app=%s",
        filename,
        mime_type,
        len(audio_bytes) / 1024,
        context.get("app_name", "unknown"),
    )

    # Build the dynamic system prompt
    system_prompt = build_system_prompt(context)
    tone = _determine_tone(context.get("app_name", "unknown"))

    # Prepare the multimodal content: system prompt (as instruction) + inline audio
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    settings = get_settings()

    generation_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.1,  # Low temp for accurate transcription
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
    )

    try:
        response = await _client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=[audio_part],
            config=generation_config,
        )

        raw_text = (response.text or "").strip()
        logger.debug("Gemini raw response: %s", raw_text[:200])

        # Parse the JSON response
        return _parse_gemini_response(raw_text, tone)

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini JSON response: %s", e)
        return {
            "processed_text": raw_text,
            "raw_transcript": raw_text,
            "tone_applied": tone,
        }
    except Exception as e:
        logger.error("Gemini API error: %s", e, exc_info=True)
        raise RuntimeError(f"Gemini processing failed: {e}") from e


def _parse_gemini_response(raw_text: str, tone: str) -> dict[str, str]:
    """
    Parse the Gemini response, handling both JSON and plain text responses.

    Args:
        raw_text: Raw text from Gemini.
        tone: The tone that was applied.

    Returns:
        Normalized response dict.
    """
    # Strip markdown code fences if Gemini wraps in ```json ... ```
    cleaned = raw_text
    if cleaned.startswith("```"):
        # Remove opening fence
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        return {
            "processed_text": parsed.get("processed_text", cleaned),
            "raw_transcript": parsed.get("raw_transcript", ""),
            "tone_applied": tone,
        }
    except json.JSONDecodeError:
        # Gemini returned plain text instead of JSON — use it directly
        logger.warning("Gemini returned non-JSON response. Using as plain text.")
        return {
            "processed_text": cleaned,
            "raw_transcript": cleaned,
            "tone_applied": tone,
        }
