"""Shared pytest configuration and fixtures."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from imap_tools import MailMessage

from src.config import Settings, settings
from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return authorization headers with the configured MCP token."""
    return {"Authorization": f"Bearer {settings.mcp_api_token}"}


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide safe environment variables for testing."""
    env = {
        "GMAIL_EMAIL": "test@gmail.com",
        "GMAIL_APP_PASSWORD": "test-password",
        "MCP_API_TOKEN": "test-mcp-token",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def fresh_settings(mock_env_vars: dict[str, str]) -> Settings:
    """Return a freshly loaded settings instance using test env vars."""
    return Settings()


@pytest.fixture
def make_mail_message() -> Generator[Any, None, None]:
    """Factory fixture for creating mocked MailMessage objects."""

    def _factory(
        *,
        uid: str = "12345",
        subject: str = "Daily Digest: Test",
        from_address: str = "informer@daily.dev",
        date: datetime | None = None,
        html: str | None = None,
        text: str | None = None,
        flags: tuple[str, ...] = (),
    ) -> MailMessage:
        email = MagicMock(spec=MailMessage)
        email.uid = uid
        email.subject = subject
        email.from_ = from_address
        email.date = date or datetime(2026, 7, 12, 9, 0, 0, tzinfo=timezone.utc)
        email.html = html
        email.text = text
        email.flags = list(flags)
        return email

    yield _factory


@pytest.fixture
def patch_settings() -> Generator[Any, None, None]:
    """Patch the global settings singleton for the duration of a test."""
    original = settings.model_copy()

    def _apply(**kwargs: Any) -> Settings:
        for key, value in kwargs.items():
            setattr(settings, key, value)
        return settings

    try:
        yield _apply
    finally:
        for key, value in original.model_dump().items():
            setattr(settings, key, value)


@pytest.fixture
def patch_imap_client() -> Generator[Any, None, None]:
    """Patch all imap_client functions used by the service."""
    with (
        patch("src.services.email_reader.get_email_by_uid") as mock_get_uid,
        patch("src.services.email_reader.get_latest_unread_email_from_sender") as mock_latest,
        patch("src.services.email_reader.mark_email_as_read") as mock_mark,
    ):
        yield {
            "get_email_by_uid": mock_get_uid,
            "get_latest_unread_email_from_sender": mock_latest,
            "mark_email_as_read": mock_mark,
        }


@pytest.fixture
async def async_http_200() -> AsyncGenerator[Any, None]:
    """Patch the httpx client to return a successful HTML response."""
    response = MagicMock()
    response.text = "<html><body><p>Article body</p></body></html>"
    response.raise_for_status.return_value = None
    with patch("src.article_scraper._client.get", return_value=response) as mock_get:
        yield mock_get
