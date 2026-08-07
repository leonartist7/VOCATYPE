"""Unit tests for the Gemini service — tone detection, prompt building, response parsing.

All tests mock the Gemini SDK; no network calls are made.
"""

from __future__ import annotations

from app.services import gemini
from app.services.gemini import (
    _determine_tone,
    _parse_gemini_response,
    build_system_prompt,
)


class TestDetermineTone:
    def test_casual_android_app(self) -> None:
        assert _determine_tone("com.whatsapp") == "casual"

    def test_casual_desktop_title(self) -> None:
        assert _determine_tone("Discord - #general") == "casual"

    def test_professional_android_app(self) -> None:
        assert _determine_tone("com.google.android.gm") == "professional"

    def test_professional_desktop_title(self) -> None:
        assert _determine_tone("Gmail - Inbox") == "professional"

    def test_neutral_unknown(self) -> None:
        assert _determine_tone("com.example.unknown") == "neutral"

    def test_case_insensitive(self) -> None:
        assert _determine_tone("WHATSAPP") == "casual"

    def test_empty_string_neutral(self) -> None:
        assert _determine_tone("") == "neutral"


class TestBuildSystemPrompt:
    def test_includes_core_instructions(self) -> None:
        prompt = build_system_prompt({})
        assert "CORE RULES" in prompt
        assert "Strip filler words" in prompt

    def test_neutral_tone_by_default(self) -> None:
        prompt = build_system_prompt({"app_name": "unknown"})
        assert "TONE: NEUTRAL" in prompt
        assert "TONE: CASUAL" not in prompt
        assert "TONE: PROFESSIONAL" not in prompt

    def test_casual_tone(self) -> None:
        prompt = build_system_prompt({"app_name": "com.whatsapp"})
        assert "TONE: CASUAL" in prompt

    def test_professional_tone(self) -> None:
        prompt = build_system_prompt({"app_name": "Gmail"})
        assert "TONE: PROFESSIONAL" in prompt

    def test_selected_text_activates_speak_to_edit(self) -> None:
        prompt = build_system_prompt({"selected_text": "make me formal"})
        assert "SPEAK-TO-EDIT MODE" in prompt
        assert "make me formal" in prompt

    def test_empty_selected_text_omits_speak_to_edit(self) -> None:
        prompt = build_system_prompt({"selected_text": "   "})
        assert "SPEAK-TO-EDIT MODE" not in prompt

    def test_language_hint_for_non_english(self) -> None:
        prompt = build_system_prompt({"language": "es"})
        assert "LANGUAGE" in prompt
        assert "es" in prompt

    def test_no_language_hint_for_english(self) -> None:
        prompt = build_system_prompt({"language": "en"})
        assert "LANGUAGE:" not in prompt


class TestParseGeminiResponse:
    def test_plain_json(self) -> None:
        raw = '{"processed_text": "Clean.", "raw_transcript": "Raw."}'
        result = _parse_gemini_response(raw, "neutral")
        assert result == {
            "processed_text": "Clean.",
            "raw_transcript": "Raw.",
            "tone_applied": "neutral",
        }

    def test_fenced_json(self) -> None:
        raw = '```json\n{"processed_text": "Clean.", "raw_transcript": "Raw."}\n```'
        result = _parse_gemini_response(raw, "casual")
        assert result["processed_text"] == "Clean."
        assert result["raw_transcript"] == "Raw."

    def test_non_json_falls_back_to_plain_text(self) -> None:
        result = _parse_gemini_response("Just plain text here.", "neutral")
        assert result["processed_text"] == "Just plain text here."
        assert result["raw_transcript"] == "Just plain text here."

    def test_missing_keys_fall_back(self) -> None:
        raw = '{"processed_text": "Only processed."}'
        result = _parse_gemini_response(raw, "professional")
        assert result["processed_text"] == "Only processed."
        assert result["raw_transcript"] == ""


class TestProcessAudioMocked:
    """Integration of process_audio with a mocked Gemini model."""

    async def test_process_audio_returns_parsed_response(self, mocker) -> None:
        fake_model = mocker.Mock()
        fake_model.generate_content_async = mocker.AsyncMock()
        fake_model.generate_content_async.return_value.text = (
            '{"processed_text": "Hello world.", "raw_transcript": "Um hello world."}'
        )

        mocker.patch.object(gemini, "_model", fake_model)
        mocker.patch.object(
            gemini,
            "build_system_prompt",
            return_value="system prompt",
        )

        result = await gemini.process_audio(
            audio_bytes=b"\x00" * 100,
            filename="test.wav",
            content_type="audio/wav",
            context={"app_name": "Gmail"},
        )

        assert result["processed_text"] == "Hello world."
        assert result["raw_transcript"] == "Um hello world."
        assert result["tone_applied"] == "professional"
        fake_model.generate_content_async.assert_awaited_once()

    async def test_process_audio_uninitialized_raises(self) -> None:
        import app.services.gemini as g

        old = g._model
        g._model = None
        try:
            try:
                await g.process_audio(
                    audio_bytes=b"x",
                    filename="x.wav",
                    content_type="audio/wav",
                    context={},
                )
            except RuntimeError as e:
                assert "not initialized" in str(e)
            else:
                raise AssertionError("Expected RuntimeError")
        finally:
            g._model = old

    async def test_process_audio_oversized_raises_value_error(self, mocker) -> None:
        mocker.patch.object(gemini, "_model", mocker.Mock())
        try:
            await gemini.process_audio(
                audio_bytes=b"\x00" * (21 * 1024 * 1024),
                filename="big.wav",
                content_type="audio/wav",
                context={},
            )
        except ValueError as e:
            assert "too large" in str(e)
        else:
            raise AssertionError("Expected ValueError")
