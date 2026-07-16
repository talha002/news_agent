"""FastAPI application exposing daily.dev email tools via MCP."""

import asyncio
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi_mcp import FastApiMCP

from src.article_scraper import fetch_article_text
from src.auth import verify_mcp_token
from src.config import settings
from src.imap_client import get_daily_dev_emails, is_email_read
from src.models import (
    ArticlesResponse,
    EmailListResponse,
    EmailSummary,
    ReadArticlesRequest,
    ReadUrlRequest,
    ReadUrlResponse,
)
from src.parsers.daily_dev import DailyDevParser
from src.services.email_reader import read_email_articles

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Daily.dev Email Reader",
    description="MCP server that reads daily.dev emails and fetches article text.",
    version="0.1.0",
)

mcp = FastApiMCP(app)
mcp.mount_sse()


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Health check endpoint (not exposed as an MCP tool)."""
    return {"status": "ok"}


@app.post(
    "/list-daily-dev-emails",
    response_model=EmailListResponse,
    dependencies=[Depends(verify_mcp_token)],
    operation_id="list_daily_dev_emails",
    summary="List unread daily.dev emails",
    description="""List unread emails from the configured daily.dev sender.

Search criteria: FROM informer@daily.dev UNSEEN (sorted by date descending, limit configurable).

MCP request example:
{
  "name": "list_daily_dev_emails",
  "arguments": {
    "limit": 10
  }
}

MCP response example:
{
  "emails": [
    {
      "uid": "12345",
      "subject": "Daily Digest: React, AI, and Cloud",
      "date": "2026-07-12T09:00:00Z",
      "from_address": "informer@daily.dev",
      "read": false
    }
  ]
}
""",
)
async def list_daily_dev_emails(limit: int = settings.default_email_limit) -> EmailListResponse:
    """Return unread daily.dev emails with their metadata."""
    try:
        emails = await asyncio.wait_for(
            asyncio.to_thread(get_daily_dev_emails, limit),
            timeout=settings.imap_timeout + 5,
        )
    except asyncio.TimeoutError as exc:
        logger.exception("IMAP request timed out while listing emails")
        raise HTTPException(
            status_code=504,
            detail=(
                "IMAP request timed out. "
                "Check network access to imap.gmail.com:993 and .env credentials."
            ),
        ) from exc

    summaries = [
        EmailSummary(
            uid=str(email.uid),
            subject=email.subject,
            date=email.date.isoformat() if email.date else "",
            from_address=email.from_,
            read=is_email_read(email),
        )
        for email in emails
    ]
    return EmailListResponse(emails=summaries)


@app.post(
    "/read-daily-dev-articles",
    response_model=ArticlesResponse,
    dependencies=[Depends(verify_mcp_token)],
    operation_id="read_daily_dev_articles",
    summary="Read daily.dev articles from an email",
    description="""Read the latest unread daily.dev email (or the email with the provided uid),
extract all 'Read article' links (author name, article header, link), fetch each article's
text, and return the result as JSON. Marks the email as read after processing.

MCP request example:
{
  "name": "read_daily_dev_articles",
  "arguments": {
    "uid": null
  }
}

MCP response example:
{
  "email_subject": "Daily Digest: React, AI, and Cloud",
  "email_date": "2026-07-12T09:00:00Z",
  "email_from": "informer@daily.dev",
  "email_uid": "12345",
  "articles": [
    {
      "author": "Vercel",
      "header": "Next.js 15 is here",
      "article_link": "https://daily.dev/blog/...",
      "article_text": "Full article text...",
      "error": null
    }
  ]
}
""",
)
async def read_daily_dev_articles(
    request: ReadArticlesRequest,
) -> ArticlesResponse:
    """Read one daily.dev email and return its articles with full text."""
    try:
        return await asyncio.wait_for(
            read_email_articles(
                parser=DailyDevParser(),
                uid=request.uid,
            ),
            timeout=settings.imap_timeout + 120,
        )
    except asyncio.TimeoutError as exc:
        logger.exception("Email processing timed out")
        raise HTTPException(
            status_code=504,
            detail=(
                "Email processing timed out. "
                "Check network access to imap.gmail.com:993 and .env credentials."
            ),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to read daily.dev articles")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/read-article-url",
    response_model=ReadUrlResponse,
    dependencies=[Depends(verify_mcp_token)],
    operation_id="read_article_url",
    summary="Fetch a single article URL",
    description="""Fetch the main readable text from a given article URL.

MCP request example:
{
  "name": "read_article_url",
  "arguments": {
    "url": "https://daily.dev/blog/..."
  }
}

MCP response example:
{
  "article_link": "https://daily.dev/blog/...",
  "article_text": "Full article text...",
  "error": null
}
""",
)
async def read_article_url(request: ReadUrlRequest) -> ReadUrlResponse:
    """Fetch a single article URL directly."""
    try:
        text = await asyncio.to_thread(fetch_article_text, str(request.url))
        return ReadUrlResponse(article_link=request.url, article_text=text, error=None)
    except Exception as exc:
        logger.exception("Failed to fetch article: %s", request.url)
        return ReadUrlResponse(article_link=request.url, article_text=None, error=str(exc))


mcp.setup_server()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
