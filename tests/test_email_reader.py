"""Tests for src/services/email_reader.py."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.parsers.daily_dev import DailyDevParser
from src.services.email_reader import _fetch_email, read_email_articles

SAMPLE_HTML = """
<html><body>
  <h2>Vercel</h2>
  <a href="https://example.com/article">Read article →</a>
</body></html>
"""


@pytest.fixture
def sample_email(make_mail_message: Any) -> Any:
    return make_mail_message(
        uid="42",
        subject="Daily Digest: Test",
        from_address="informer@daily.dev",
        html=SAMPLE_HTML,
        text=None,
    )


@pytest.mark.asyncio
async def test_read_email_articles_success(
    patch_imap_client: dict[str, MagicMock],
    sample_email: Any,
) -> None:
    patch_imap_client["get_latest_unread_email_from_sender"].return_value = [sample_email]

    with patch(
        "src.services.email_reader.fetch_article_text",
        return_value="Article body",
    ):
        response = await read_email_articles(parser=DailyDevParser())

    assert response.email_uid == "42"
    assert response.email_subject == "Daily Digest: Test"
    assert len(response.articles) == 1
    assert response.articles[0].author == "Vercel"
    assert response.articles[0].article_text == "Article body"
    patch_imap_client["mark_email_as_read"].assert_called_once_with("42")


@pytest.mark.asyncio
async def test_read_email_articles_by_uid(
    patch_imap_client: dict[str, MagicMock],
    sample_email: Any,
) -> None:
    patch_imap_client["get_email_by_uid"].return_value = sample_email

    with patch(
        "src.services.email_reader.fetch_article_text",
        return_value="Article body",
    ):
        response = await read_email_articles(parser=DailyDevParser(), uid="42")

    patch_imap_client["get_email_by_uid"].assert_called_once_with("42")
    assert response.email_uid == "42"


@pytest.mark.asyncio
async def test_read_email_articles_fetch_error(
    patch_imap_client: dict[str, MagicMock],
) -> None:
    patch_imap_client["get_latest_unread_email_from_sender"].return_value = []

    with pytest.raises(HTTPException) as exc_info:
        await read_email_articles(parser=DailyDevParser())
    assert exc_info.value.status_code == 404
    assert "No unread emails" in exc_info.value.detail


@pytest.mark.asyncio
async def test_read_email_articles_uid_mismatch(
    patch_imap_client: dict[str, MagicMock],
    make_mail_message: Any,
) -> None:
    email = make_mail_message(
        uid="42",
        from_address="wrong@example.com",
        html=SAMPLE_HTML,
    )
    patch_imap_client["get_email_by_uid"].return_value = email

    with pytest.raises(HTTPException) as exc_info:
        await read_email_articles(parser=DailyDevParser(), uid="42")
    assert exc_info.value.status_code == 404
    assert "does not match parser" in exc_info.value.detail


@pytest.mark.asyncio
async def test_read_email_articles_scrape_error(
    patch_imap_client: dict[str, MagicMock],
    sample_email: Any,
) -> None:
    patch_imap_client["get_latest_unread_email_from_sender"].return_value = [sample_email]

    with patch(
        "src.services.email_reader.fetch_article_text",
        side_effect=RuntimeError("Network error"),
    ):
        response = await read_email_articles(parser=DailyDevParser())

    assert len(response.articles) == 1
    assert response.articles[0].error == "Network error"
    assert response.articles[0].article_text is None


@pytest.mark.asyncio
async def test_fetch_email_by_uid_not_found(
    patch_imap_client: dict[str, MagicMock],
) -> None:
    patch_imap_client["get_email_by_uid"].return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await _fetch_email(DailyDevParser(), uid="99")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_email_no_unread(
    patch_imap_client: dict[str, MagicMock],
) -> None:
    patch_imap_client["get_latest_unread_email_from_sender"].return_value = []

    with pytest.raises(HTTPException) as exc_info:
        await _fetch_email(DailyDevParser())
    assert exc_info.value.status_code == 404
    assert "No unread emails" in exc_info.value.detail
