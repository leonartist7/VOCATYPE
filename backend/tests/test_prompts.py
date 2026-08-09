"""Unit tests for the shared prompt builder — tone detection and prompt assembly."""

from __future__ import annotations

from app.services.prompts import build_system_prompt, determine_tone


class TestDetermineTone:
    def test_casual_apps(self):
        assert determine_tone("whatsapp") == "casual"
        assert determine_tone("com.whatsapp") == "casual"
        assert determine_tone("Discord") == "casual"
        assert determine_tone("com.zhiliaoapp.musically") == "casual"

    def test_professional_apps(self):
        assert determine_tone("gmail") == "professional"
        assert determine_tone("com.google.android.gm") == "professional"
        assert determine_tone("Notion") == "professional"
        assert determine_tone("Microsoft Outlook") == "professional"

    def test_unknown_app_neutral(self):
        assert determine_tone("random-app") == "neutral"
        assert determine_tone("") == "neutral"


class TestBuildSystemPrompt:
    def test_contains_core_rules(self):
        prompt = build_system_prompt({"app_name": "gmail"})
        assert "Add punctuation" in prompt
        assert "Strip filler words" in prompt
        assert "Fix grammar" in prompt

    def test_tone_layer(self):
        casual = build_system_prompt({"app_name": "whatsapp"})
        assert "TONE: CASUAL" in casual

        prof = build_system_prompt({"app_name": "gmail"})
        assert "TONE: PROFESSIONAL" in prof

        neutral = build_system_prompt({"app_name": "xyz"})
        assert "TONE: NEUTRAL" in neutral

    def test_speak_to_edit_layer(self):
        prompt = build_system_prompt({"app_name": "gmail", "selected_text": "Hello there."})
        assert "SPEAK-TO-EDIT MODE" in prompt
        assert "Hello there." in prompt

        plain = build_system_prompt({"app_name": "gmail"})
        assert "SPEAK-TO-EDIT MODE" not in plain

    def test_language_hint(self):
        prompt = build_system_prompt({"app_name": "gmail", "language": "es"})
        assert "LANGUAGE" in prompt

        en = build_system_prompt({"app_name": "gmail", "language": "en"})
        assert "LANGUAGE" not in en
