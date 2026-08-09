"""
Shared prompt-building logic for the online text-cleaning engine.

Given a raw transcript and request context, builds the system prompt used by
the LLM to strip filler words, fix punctuation/grammar, apply tone, and handle
speak-to-edit commands.
"""

from __future__ import annotations

import logging
from typing import Any

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


def determine_tone(app_name: str) -> str:
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

_BASE_INSTRUCTIONS = """You are Vocatype, a dictation cleaning engine. You receive a raw speech-to-text transcript and convert it into clean, properly formatted text.

CORE RULES — ALWAYS FOLLOW:
1. **Add punctuation**: Insert all missing periods, commas, question marks, and capitalization. Group run-on speech into sentences.
2. **Strip filler words**: Remove all "um", "uh", "er", "ah", "like" (when used as filler), "you know", "I mean", "basically", "actually" (when filler), "sort of", "kind of" (when filler), repeated words, false starts, and hesitations.
3. **Fix grammar**: Correct subject-verb agreement, tense consistency, and punctuation. Add proper capitalization.
4. **Preserve intent**: Never change the meaning of what the user said. Only clean up delivery.
5. **Auto-format**: If the user dictates a list (e.g., "first... second... third..." or "number one... number two..."), format it as a properly structured list with bullet points or numbers.
6. **Paragraph breaks**: Insert paragraph breaks at natural topic transitions.
7. **No meta-commentary**: Output ONLY the processed text. Never say "Here's the cleaned text:" or add any explanation.

RESPONSE FORMAT:
You MUST respond with valid JSON only. No markdown, no code fences, no extra text.
{
  "processed_text": "The final cleaned text"
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
    tone = determine_tone(app_name)

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
            f"Clean and process the text in that language unless the command says otherwise."
        )

    prompt = "\n\n".join(parts)
    logger.debug(
        "Built system prompt (%d chars) for app='%s', tone='%s'", len(prompt), app_name, tone
    )
    return prompt
