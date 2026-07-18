"""Tests for src/main.py."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import mcp
from src.models import Article, ArticlesResponse


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
def fresh_mcp_session_manager() -> None:
    """Reset fastapi-mcp's lazy HTTP session manager between tests.

    TestClient cancels the manager's background task after each request, so
    clear the started flag to let the next request spin up a fresh manager.
    """
    mcp._http_transport._manager_started = False


def _mcp_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    return {
        **auth_headers,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _initialize_body() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.0.1"},
        },
    }


def test_mcp_initialize_handshake(
    client: TestClient, auth_headers: dict[str, str], fresh_mcp_session_manager: None
) -> None:
    response = client.post("/mcp", json=_initialize_body(), headers=_mcp_headers(auth_headers))

    assert response.status_code == 200
    assert "mcp-session-id" in response.headers
    result = response.json()["result"]
    assert result["protocolVersion"]
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "Daily.dev Email Reader"


def test_mcp_rejects_non_initialize_without_session(
    client: TestClient, fresh_mcp_session_manager: None
) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 400


def test_sse_endpoint_removed(client: TestClient) -> None:
    assert client.get("/sse").status_code == 404
    assert client.post("/sse").status_code == 404


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
