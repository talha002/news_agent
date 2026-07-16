"""IMAP client for reading and marking daily.dev emails."""

import logging
from typing import List, Optional

from imap_tools import AND, MailBox, MailMessage, MailMessageFlags

from src.config import settings

logger = logging.getLogger(__name__)


def _get_mailbox() -> MailBox:
    """Create and login to the Gmail IMAP mailbox."""
    mailbox = MailBox(settings.gmail_imap_server, timeout=settings.imap_timeout)
    mailbox.login(settings.gmail_email, settings.gmail_app_password)
    return mailbox


def get_daily_dev_emails(limit: int = 10) -> List[MailMessage]:
    """Fetch unread emails from the configured daily.dev sender."""
    return get_unread_emails_from_sender(settings.daily_dev_sender, limit)


def get_unread_emails_from_sender(sender: str, limit: int = 10) -> List[MailMessage]:
    """Fetch unread emails from a specific sender, sorted by date descending."""
    with _get_mailbox() as mailbox:
        criteria = AND(from_=sender, seen=False)
        emails = list(
            mailbox.fetch(
                criteria,
                limit=limit,
                reverse=True,
                mark_seen=False,
            )
        )
        logger.info("Fetched %d unread emails from %s", len(emails), sender)
        return emails


def get_latest_unread_email_from_sender(sender: str) -> List[MailMessage]:
    """Return the single latest unread email from *sender*, or empty list."""
    return get_unread_emails_from_sender(sender, limit=1)


def get_email_by_uid(uid: str) -> Optional[MailMessage]:
    """Fetch a single email by its IMAP UID."""
    with _get_mailbox() as mailbox:
        emails = list(mailbox.fetch(AND(uid=uid), mark_seen=False))
        if not emails:
            logger.warning("Email with uid %s not found", uid)
            return None
        return emails[0]


def mark_email_as_read(uid: str) -> None:
    """Set the Seen flag on the email with the given UID."""
    with _get_mailbox() as mailbox:
        mailbox.flag([uid], MailMessageFlags.SEEN, True)
        logger.info("Marked email %s as read", uid)


def is_email_read(email: MailMessage) -> bool:
    """Check whether the message has the Seen flag."""
    return MailMessageFlags.SEEN in (email.flags or [])
