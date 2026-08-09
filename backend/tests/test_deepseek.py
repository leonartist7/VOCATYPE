"""Unit tests for the DeepSeek cleaning service.

All tests mock the httpx client; no network calls are made.
"""

from __future__ import annotations

import pytest

from app.services import deepseek


class FakeResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {
            "choices": [{"message": {"content": '{"processed_text": "Hello world."}'}}]
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._body


class TestParseDeepseekResponse:
    def test_parses_json(self):
        result = deepseek._parse_deepseek_response('{"processed_text": "Hello world."}', "neutral")
        assert result == {"processed_text": "Hello world.", "tone_applied": "neutral"}

    def test_strips_code_fences(self):
        raw = '```json\n{"processed_text": "Hello."}\n```'
        result = deepseek._parse_deepseek_response(raw, "casual")
        assert result["processed_text"] == "Hello."

    def test_plain_text_fallback(self):
        result = deepseek._parse_deepseek_response("Just plain text here.", "neutral")
        assert result["processed_text"] == "Just plain text here."
        assert result["tone_applied"] == "neutral"


class TestCleanTranscript:
    @pytest.mark.asyncio
    async def test_success_with_mocked_client(self, mocker):
        fake_client = mocker.Mock(is_closed=False)
        fake_client.post = mocker.AsyncMock(return_value=FakeResponse())
        mocker.patch.object(deepseek, "_client", fake_client)
        mocker.patch(
            "app.services.deepseek.get_settings",
            return_value=type(
                "S",
                (),
                {
                    "deepseek_api_key": "key",
                    "deepseek_model": "deepseek-v4-flash",
                    "deepseek_base_url": "https://api.deepseek.com",
                },
            )(),
        )

        result = await deepseek.clean_transcript("um hello", {"app_name": "gmail"})
        assert result["processed_text"] == "Hello world."
        assert result["tone_applied"] == "professional"

        call_kwargs = fake_client.post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "deepseek-v4-flash"
        assert call_kwargs["json"]["thinking"] == {"type": "disabled"}
        assert call_kwargs["json"]["messages"][1]["content"] == "um hello"

    @pytest.mark.asyncio
    async def test_missing_key_raises(self, mocker):
        mocker.patch.object(deepseek, "_client", mocker.Mock(is_closed=False))
        mocker.patch(
            "app.services.deepseek.get_settings",
            return_value=type(
                "S",
                (),
                {
                    "deepseek_api_key": "",
                    "deepseek_model": "deepseek-v4-flash",
                    "deepseek_base_url": "https://api.deepseek.com",
                },
            )(),
        )
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            await deepseek.clean_transcript("hello", {"app_name": "x"})

    @pytest.mark.asyncio
    async def test_api_error_raises_runtime_error(self, mocker):
        fake_client = mocker.Mock(is_closed=False)
        fake_client.post.side_effect = Exception("connection refused")
        mocker.patch.object(deepseek, "_client", fake_client)
        mocker.patch(
            "app.services.deepseek.get_settings",
            return_value=type(
                "S",
                (),
                {
                    "deepseek_api_key": "key",
                    "deepseek_model": "deepseek-v4-flash",
                    "deepseek_base_url": "https://api.deepseek.com",
                },
            )(),
        )
        with pytest.raises(RuntimeError, match="DeepSeek cleaning failed"):
            await deepseek.clean_transcript("hello", {"app_name": "x"})

    @pytest.mark.asyncio
    async def test_init_creates_client_if_missing(self, mocker):
        mocker.patch("httpx.AsyncClient")
        mocker.patch.object(deepseek, "_client", None)
        mocker.patch(
            "app.services.deepseek.get_settings",
            return_value=type(
                "S",
                (),
                {
                    "deepseek_api_key": "key",
                    "deepseek_model": "deepseek-v4-flash",
                    "deepseek_base_url": "https://api.deepseek.com",
                },
            )(),
        )
        deepseek.initialize_deepseek()
        assert deepseek._client is not None


def test_determine_tone_mapping():
    from app.services.prompts import determine_tone

    assert determine_tone("gmail") == "professional"
    assert determine_tone("whatsapp") == "casual"
    assert determine_tone("random-app") == "neutral"
