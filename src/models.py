"""Pydantic response/request models for the MCP tools."""

from pydantic import BaseModel, Field, HttpUrl


class EmailSummary(BaseModel):
    uid: str = Field(..., description="IMAP UID of the email")
    subject: str = Field(..., description="Email subject line")
    date: str = Field(..., description="Email date in ISO-8601 format")
    from_address: str = Field(..., description="Sender email address")
    read: bool = Field(..., description="Whether the email has been marked as read")

    model_config = {
        "json_schema_extra": {
            "example": {
                "uid": "12345",
                "subject": "Daily Digest: React, AI, and Cloud",
                "date": "2026-07-12T09:00:00Z",
                "from_address": "informer@daily.dev",
                "read": False,
            }
        }
    }


class Article(BaseModel):
    author: str = Field(..., description="Author or source that published the article")
    header: str = Field(..., description="Article title/header")
    article_link: HttpUrl = Field(..., description="URL pointing to the full article")
    article_text: str | None = Field(
        None, description="Extracted main text of the article"
    )
    error: str | None = Field(
        None, description="Error message if article text could not be fetched"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "author": "Vercel",
                "header": "Next.js 15 is here",
                "article_link": "https://daily.dev/blog/...",
                "article_text": "Full article text...",
                "error": None,
            }
        }
    }


class ArticlesResponse(BaseModel):
    email_subject: str = Field(..., description="Subject of the processed email")
    email_date: str = Field(..., description="Date of the processed email")
    email_from: str = Field(..., description="Sender of the processed email")
    email_uid: str = Field(..., description="IMAP UID of the processed email")
    articles: list[Article] = Field(..., description="Articles found in the email")

    model_config = {
        "json_schema_extra": {
            "example": {
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
                        "error": None,
                    }
                ],
            }
        }
    }


class EmailListResponse(BaseModel):
    emails: list[EmailSummary] = Field(..., description="List of matching emails")

    model_config = {
        "json_schema_extra": {
            "example": {
                "emails": [
                    {
                        "uid": "12345",
                        "subject": "Daily Digest: React, AI, and Cloud",
                        "date": "2026-07-12T09:00:00Z",
                        "from_address": "informer@daily.dev",
                        "read": False,
                    }
                ]
            }
        }
    }


class ReadArticlesRequest(BaseModel):
    uid: str | None = Field(
        None,
        description="IMAP UID of the email to read. If omitted, the latest unread email is used.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "uid": None,
            }
        }
    }


class ReadUrlRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the article to fetch")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://daily.dev/blog/...",
            }
        }
    }


class ReadUrlResponse(BaseModel):
    article_link: HttpUrl = Field(..., description="Requested article URL")
    article_text: str | None = Field(None, description="Extracted main text of the article")
    error: str | None = Field(
        None, description="Error message if article text could not be fetched"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "article_link": "https://daily.dev/blog/...",
                "article_text": "Full article text...",
                "error": None,
            }
        }
    }
