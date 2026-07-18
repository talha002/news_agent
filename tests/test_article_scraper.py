"""Tests for src/article_scraper.py."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.article_scraper import _clean_text, fetch_article_text


class TestCleanText:
    def test_collapses_blank_lines(self) -> None:
        text = "Line 1\n\n\n\nLine 2\r\nLine 3"
        cleaned = _clean_text(text)
        assert cleaned == "Line 1\n\nLine 2\nLine 3"

    def test_trims_whitespace(self) -> None:
        assert _clean_text("  hello\n\n  ") == "hello"


class TestFetchArticleText:
    def test_fetch_article_text_success(self) -> None:
        response = MagicMock()
        response.text = "<html><body><p>Article content</p></body></html>"
        response.raise_for_status.return_value = None

        with patch("src.article_scraper._client.get", return_value=response) as mock_get:
            text = fetch_article_text("https://example.com/article")
            mock_get.assert_called_once()
            assert "Article content" in text

    def test_fetch_article_text_network_error(self) -> None:
        with patch(
            "src.article_scraper._client.get",
            side_effect=httpx.ConnectError("Connection failed"),
        ):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                fetch_article_text("https://example.com/article")

    def test_fetch_article_text_http_error(self) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )

        with patch("src.article_scraper._client.get", return_value=response):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                fetch_article_text("https://example.com/article")

    def test_fetch_article_text_respects_max_length(self, patch_settings: Any) -> None:
        patch_settings(max_article_length=20)
        response = MagicMock()
        response.text = "<html><body><p>" + "a" * 100 + "</p></body></html>"
        response.raise_for_status.return_value = None

        with patch("src.article_scraper._client.get", return_value=response):
            text = fetch_article_text("https://example.com/article")
            assert len(text) <= 20

    def test_fetch_article_text_follows_redirects(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/old":
                return httpx.Response(302, headers={"Location": "/new"})
            return httpx.Response(
                200, text="<html><body><p>Redirected content</p></body></html>"
            )

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        )
        with patch("src.article_scraper._client", client):
            text = fetch_article_text("https://example.com/old")
            assert "Redirected content" in text

    def test_fetch_article_text_daily_dev_next_data(self) -> None:
        next_data = {
            "props": {
                "pageProps": {
                    "initialData": {
                        "post": {
                            "summary": "Daily.dev summary text",
                        }
                    }
                }
            }
        }
        html = (
            '<html><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(next_data)
            + "</script></body></html>"
        )
        response = MagicMock()
        response.text = html
        response.url = "https://app.daily.dev/posts/abc123"
        response.raise_for_status.return_value = None

        with patch("src.article_scraper._client.get", return_value=response):
            text = fetch_article_text("https://app.daily.dev/posts/abc123")
            assert "Daily.dev summary text" in text
