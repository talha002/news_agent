"""Tests for src/article_scraper.py."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

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

        with patch("src.article_scraper.requests.get", return_value=response) as mock_get:
            text = fetch_article_text("https://example.com/article")
            mock_get.assert_called_once()
            assert "Article content" in text

    def test_fetch_article_text_network_error(self) -> None:
        with patch(
            "src.article_scraper.requests.get",
            side_effect=requests.RequestException("Connection failed"),
        ):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                fetch_article_text("https://example.com/article")

    def test_fetch_article_text_http_error(self) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch("src.article_scraper.requests.get", return_value=response):
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                fetch_article_text("https://example.com/article")

    def test_fetch_article_text_respects_max_length(self, patch_settings: Any) -> None:
        patch_settings(max_article_length=20)
        response = MagicMock()
        response.text = "<html><body><p>" + "a" * 100 + "</p></body></html>"
        response.raise_for_status.return_value = None

        with patch("src.article_scraper.requests.get", return_value=response):
            text = fetch_article_text("https://example.com/article")
            assert len(text) <= 20
