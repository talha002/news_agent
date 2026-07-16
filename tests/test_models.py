"""Tests for src/models.py."""

import pytest
from pydantic import ValidationError

from src.models import (
    Article,
    ArticlesResponse,
    EmailListResponse,
    EmailSummary,
    ReadArticlesRequest,
    ReadUrlRequest,
    ReadUrlResponse,
)


def test_email_summary_creation() -> None:
    summary = EmailSummary(
        uid="1",
        subject="Test",
        date="2026-07-12T09:00:00Z",
        from_address="informer@daily.dev",
        read=False,
    )
    assert summary.uid == "1"
    assert not summary.read


def test_article_requires_link() -> None:
    """Article requires a valid HTTP/HTTPS URL."""
    with pytest.raises(ValidationError):
        Article(author="ACME", header="Title", article_link="not-a-url")

    article = Article(
        author="ACME",
        header="Title",
        article_link="https://example.com/article",
    )
    assert str(article.article_link) == "https://example.com/article"


def test_articles_response_requires_articles() -> None:
    response = ArticlesResponse(
        email_subject="Subject",
        email_date="2026-07-12T09:00:00Z",
        email_from="informer@daily.dev",
        email_uid="42",
        articles=[
            Article(
                author="ACME",
                header="Title",
                article_link="https://example.com/article",
            )
        ],
    )
    assert len(response.articles) == 1
    assert response.email_uid == "42"


def test_email_list_response_empty() -> None:
    response = EmailListResponse(emails=[])
    assert response.emails == []


def test_read_articles_request_uid_optional() -> None:
    request = ReadArticlesRequest()
    assert request.uid is None

    request = ReadArticlesRequest(uid="999")
    assert request.uid == "999"


def test_read_url_request_valid_url() -> None:
    request = ReadUrlRequest(url="https://example.com/article")
    assert str(request.url) == "https://example.com/article"


def test_read_url_request_invalid_url() -> None:
    with pytest.raises(ValidationError):
        ReadUrlRequest(url="ftp://example.com/article")


def test_read_url_response_creation() -> None:
    response = ReadUrlResponse(
        article_link="https://example.com/article",
        article_text="Body",
        error=None,
    )
    assert response.article_text == "Body"
    assert response.error is None
