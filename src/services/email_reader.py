"""Shared orchestration service for reading emails with any parser."""

import asyncio
import logging

from fastapi import HTTPException
from imap_tools import MailMessage

from src.article_scraper import fetch_article_text
from src.imap_client import (
    get_email_by_uid,
    get_latest_unread_email_from_sender,
    mark_email_as_read,
)
from src.models import ArticlesResponse
from src.parsers.base import EmailParser

logger = logging.getLogger(__name__)


async def read_email_articles(parser: EmailParser, uid: str | None = None) -> ArticlesResponse:
    """Fetch, parse, scrape, and optionally mark-read an email using *parser*.

    If *uid* is provided, the specific email is fetched and validated against
    the parser. If *uid* is omitted, the latest unread email from the parser's
    configured sender is used. The email is always marked as read after parsing.
    """
    email = await _fetch_email(parser, uid)

    articles = parser.parse(email)

    for article in articles:
        try:
            article.article_text = await asyncio.to_thread(
                fetch_article_text, str(article.article_link)
            )
        except Exception as exc:
            logger.exception("Failed to fetch article: %s", article.article_link)
            article.error = str(exc)
            article.article_text = None

    await asyncio.to_thread(mark_email_as_read, str(email.uid))

    return ArticlesResponse(
        email_subject=email.subject,
        email_date=email.date.isoformat() if email.date else "",
        email_from=email.from_,
        email_uid=str(email.uid),
        articles=articles,
    )


async def _fetch_email(parser: EmailParser, uid: str | None = None) -> MailMessage:
    """Resolve the MailMessage to process."""
    if uid:
        email = await asyncio.to_thread(get_email_by_uid, uid)
        if not email or not parser.can_parse(email):
            raise HTTPException(
                status_code=404,
                detail=f"Email not found or does not match parser '{parser.name}'",
            )
        return email

    emails = await asyncio.to_thread(get_latest_unread_email_from_sender, parser.sender)
    if not emails:
        raise HTTPException(
            status_code=404,
            detail=f"No unread emails from {parser.sender}",
        )
    return emails[0]
