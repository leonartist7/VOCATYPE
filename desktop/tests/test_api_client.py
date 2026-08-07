"""Unit tests for the desktop API client (HTTP mocked)."""

from __future__ import annotations

from unittest import mock

from app import api_client


class TestSendAudio:
    def test_success_returns_processed_text(self) -> None:
        fake_client = mock.Mock()
        fake_client.post.return_value = mock.Mock(
            status_code=200,
            json=lambda: {"processed_text": "Hello.", "tone_applied": "neutral"},
            text="",
        )
        with mock.patch.object(api_client, "_get_client", return_value=fake_client):
            result = api_client.send_audio(b"wavdata", {"app_name": "Gmail"})
        assert result == "Hello."
        fake_client.post.assert_called_once()
        # The request must include the multipart file and context JSON
        kwargs = fake_client.post.call_args.kwargs
        assert "/process-audio" in fake_client.post.call_args.args
        assert "audio_file" in kwargs["files"]
        assert "context" in kwargs["data"]

    def test_client_error_returns_none_no_retry(self) -> None:
        fake_client = mock.Mock()
        fake_client.post.return_value = mock.Mock(
            status_code=400,
            json=lambda: {},
            text="bad request",
        )
        with mock.patch.object(api_client, "_get_client", return_value=fake_client):
            result = api_client.send_audio(b"wavdata", {})
        assert result is None
        assert fake_client.post.call_count == 1  # no retry on 4xx

    def test_retries_on_connection_error(self) -> None:
        fake_client = mock.Mock()
        fake_client.post.side_effect = [
            mock.Mock(side_effect=Exception("connection refused")),
            mock.Mock(
                status_code=200,
                json=lambda: {"processed_text": "retried ok", "tone_applied": "neutral"},
                text="",
            ),
        ]
        with mock.patch.object(api_client, "_get_client", return_value=fake_client):
            result = api_client.send_audio(b"wavdata", {}, max_retries=2)
        assert result == "retried ok"
        assert fake_client.post.call_count == 2

    def test_all_attempts_fail_returns_none(self) -> None:
        fake_client = mock.Mock()
        fake_client.post.side_effect = [
            mock.Mock(side_effect=Exception("timeout")),
            mock.Mock(side_effect=Exception("timeout")),
            mock.Mock(side_effect=Exception("timeout")),
        ]
        with mock.patch.object(api_client, "_get_client", return_value=fake_client):
            result = api_client.send_audio(b"wavdata", {}, max_retries=3)
        assert result is None


class TestCloseClient:
    def test_close_closes_and_resets(self) -> None:
        fake_client = mock.Mock()
        fake_client.is_closed = False
        with mock.patch.object(api_client, "_client", fake_client):
            api_client.close_client()
        fake_client.close.assert_called_once()
