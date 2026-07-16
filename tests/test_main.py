"""Tests for src/main.py."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.models import Article, ArticlesResponse


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_daily_dev_emails_requires_auth(client: TestClient) -> None:
    response = client.post("/list-daily-dev-emails")
    assert response.status_code == 401


def test_list_daily_dev_emails_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    email = MagicMock()
    email.uid = "1"
    email.subject = "Daily Digest"
    email.from_ = "informer@daily.dev"
    email.date = datetime(2026, 7, 12, 9, 0, 0, tzinfo=timezone.utc)
    email.flags = []

    with patch("src.main.get_daily_dev_emails", return_value=[email]):
        response = client.post("/list-daily-dev-emails", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["emails"]) == 1
    assert data["emails"][0]["uid"] == "1"
    assert not data["emails"][0]["read"]


def test_list_daily_dev_emails_timeout(
    client: TestClient, auth_headers: dict[str, str], patch_settings: Any
) -> None:
    patch_settings(imap_timeout=1)

    def _hang(*_args: Any, **_kwargs: Any) -> list[Any]:
        import time

        time.sleep(10)
        return []

    with patch("src.main.get_daily_dev_emails", side_effect=_hang):
        response = client.post("/list-daily-dev-emails", headers=auth_headers)

    assert response.status_code == 504
    assert "IMAP request timed out" in response.json()["detail"]


def test_read_daily_dev_articles_requires_auth(client: TestClient) -> None:
    response = client.post("/read-daily-dev-articles", json={"uid": None})
    assert response.status_code == 401


def test_read_daily_dev_articles_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = ArticlesResponse(
        email_subject="Daily Digest",
        email_date="2026-07-12T09:00:00Z",
        email_from="informer@daily.dev",
        email_uid="42",
        articles=[
            Article(
                author="Vercel",
                header="Next.js 15",
                article_link="https://example.com/article",
                article_text="Body",
            )
        ],
    )

    with patch("src.main.read_email_articles", return_value=response):
        resp = client.post(
            "/read-daily-dev-articles",
            headers=auth_headers,
            json={"uid": None},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email_uid"] == "42"
    assert data["articles"][0]["author"] == "Vercel"


def test_read_daily_dev_articles_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    from fastapi import HTTPException

    with patch("src.main.read_email_articles", side_effect=HTTPException(status_code=404)):
        resp = client.post(
            "/read-daily-dev-articles",
            headers=auth_headers,
            json={"uid": None},
        )
    assert resp.status_code == 404


def test_read_article_url_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/read-article-url",
        json={"url": "https://example.com/article"},
    )
    assert response.status_code == 401


def test_read_article_url_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    with patch("src.main.fetch_article_text", return_value="Article body"):
        response = client.post(
            "/read-article-url",
            headers=auth_headers,
            json={"url": "https://example.com/article"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["article_text"] == "Article body"
    assert data["error"] is None


def test_read_article_url_fetch_error(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    with patch(
        "src.main.fetch_article_text",
        side_effect=RuntimeError("Network error"),
    ):
        response = client.post(
            "/read-article-url",
            headers=auth_headers,
            json={"url": "https://example.com/article"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["article_text"] is None
    assert "Network error" in data["error"]


def test_read_article_url_invalid_url(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/read-article-url",
        headers=auth_headers,
        json={"url": "not-a-url"},
    )
    assert response.status_code == 422
