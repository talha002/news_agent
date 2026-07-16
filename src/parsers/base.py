"""Shared parser protocol."""

from typing import Protocol, runtime_checkable

from imap_tools import MailMessage

from src.models import Article


@runtime_checkable
class EmailParser(Protocol):
    """Protocol every email-source parser must implement."""

    name: str
    sender: str

    def can_parse(self, email: MailMessage) -> bool:
        """Return True if this parser handles the given email."""
        ...

    def parse(self, email: MailMessage) -> list[Article]:
        """Extract articles from the email body."""
        ...
