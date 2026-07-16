"""Tests for src/imap_client.py."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from imap_tools import MailMessageFlags

from src.config import settings
from src.imap_client import (
    _get_mailbox,
    get_daily_dev_emails,
    get_email_by_uid,
    get_latest_unread_email_from_sender,
    get_unread_emails_from_sender,
    is_email_read,
    mark_email_as_read,
)


def test_get_mailbox_login() -> None:
    """_get_mailbox creates a MailBox and logs in with configured credentials."""
    with patch("src.imap_client.MailBox") as mock_mailbox_class:
        mailbox = MagicMock()
        mock_mailbox_class.return_value = mailbox

        result = _get_mailbox()

        mock_mailbox_class.assert_called_once_with(
            settings.gmail_imap_server,
            timeout=settings.imap_timeout,
        )
        mailbox.login.assert_called_once()
        assert result is mailbox


def test_get_daily_dev_emails() -> None:
    """get_daily_dev_emails delegates to the sender-specific fetch."""
    with patch("src.imap_client.get_unread_emails_from_sender") as mock_fetch:
        mock_fetch.return_value = []
        get_daily_dev_emails(limit=5)
        mock_fetch.assert_called_once_with("informer@daily.dev", 5)


def test_get_unread_emails_from_sender() -> None:
    email = MagicMock()
    email.uid = "1"
    email.subject = "Subject"
    email.from_ = "informer@daily.dev"
    email.date = datetime(2026, 7, 12, 9, 0, 0, tzinfo=timezone.utc)
    email.flags = []

    with patch("src.imap_client.MailBox") as mock_mailbox_class:
        mailbox = MagicMock()
        mailbox.__enter__ = MagicMock(return_value=mailbox)
        mailbox.__exit__ = MagicMock(return_value=False)
        mailbox.fetch.return_value = [email]
        mock_mailbox_class.return_value = mailbox

        result = get_unread_emails_from_sender("informer@daily.dev", limit=10)
        assert len(result) == 1
        assert result[0].uid == "1"
        mailbox.fetch.assert_called_once()
        _, kwargs = mailbox.fetch.call_args
        assert kwargs.get("mark_seen") is False
        assert kwargs.get("reverse") is True
        assert kwargs.get("limit") == 10


def test_get_latest_unread_email_from_sender() -> None:
    with patch("src.imap_client.get_unread_emails_from_sender") as mock_fetch:
        mock_fetch.return_value = []
        get_latest_unread_email_from_sender("informer@daily.dev")
        mock_fetch.assert_called_once_with("informer@daily.dev", limit=1)


def test_get_email_by_uid_found() -> None:
    email = MagicMock()
    email.uid = "42"
    with patch("src.imap_client.MailBox") as mock_mailbox_class:
        mailbox = MagicMock()
        mailbox.__enter__ = MagicMock(return_value=mailbox)
        mailbox.__exit__ = MagicMock(return_value=False)
        mailbox.fetch.return_value = [email]
        mock_mailbox_class.return_value = mailbox

        result = get_email_by_uid("42")
        assert result is email


def test_get_email_by_uid_not_found() -> None:
    with patch("src.imap_client.MailBox") as mock_mailbox_class:
        mailbox = MagicMock()
        mailbox.__enter__ = MagicMock(return_value=mailbox)
        mailbox.__exit__ = MagicMock(return_value=False)
        mailbox.fetch.return_value = []
        mock_mailbox_class.return_value = mailbox

        assert get_email_by_uid("99") is None


def test_mark_email_as_read() -> None:
    with patch("src.imap_client.MailBox") as mock_mailbox_class:
        mailbox = MagicMock()
        mailbox.__enter__ = MagicMock(return_value=mailbox)
        mailbox.__exit__ = MagicMock(return_value=False)
        mock_mailbox_class.return_value = mailbox

        mark_email_as_read("42")
        mailbox.flag.assert_called_once()
        args = mailbox.flag.call_args[0]
        assert args[0] == ["42"]
        assert args[1] is MailMessageFlags.SEEN
        assert args[2] is True


def test_is_email_read_true() -> None:
    email = MagicMock()
    email.flags = [MailMessageFlags.SEEN]
    assert is_email_read(email) is True


def test_is_email_read_false() -> None:
    email = MagicMock()
    email.flags = []
    assert is_email_read(email) is False


def test_is_email_read_no_flags() -> None:
    email = MagicMock()
    email.flags = None
    assert is_email_read(email) is False
