"""Tests for src/config.py."""

import pytest

from src.config import Settings, settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default values are applied when optional env vars are missing."""
    monkeypatch.setenv("GMAIL_EMAIL", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("MCP_API_TOKEN", "token")
    # Ensure optional env vars are not present
    for key in ("HOST", "PORT", "LOG_LEVEL", "DAILY_DEV_SENDER"):
        monkeypatch.delenv(key, raising=False)

    fresh = Settings()
    assert fresh.gmail_email == "a@gmail.com"
    assert fresh.gmail_app_password == "pw"
    assert fresh.mcp_api_token == "token"
    assert fresh.host == "0.0.0.0"
    assert fresh.port == 8000
    assert fresh.log_level == "info"
    assert fresh.daily_dev_sender == "informer@daily.dev"
    assert fresh.default_email_limit == 10
    assert fresh.request_timeout == 30
    assert fresh.max_article_length == 20000


def test_settings_gmail_imap_server() -> None:
    """The IMAP server property returns the expected Gmail server."""
    assert settings.gmail_imap_server == "imap.gmail.com"


def test_settings_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional values can be overridden via environment variables."""
    monkeypatch.setenv("GMAIL_EMAIL", "a@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("MCP_API_TOKEN", "token")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("DEFAULT_EMAIL_LIMIT", "5")

    fresh = Settings()
    assert fresh.host == "127.0.0.1"
    assert fresh.port == 9000
    assert fresh.default_email_limit == 5
