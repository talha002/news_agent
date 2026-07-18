"""Fetch and extract main article text from a URL."""

import json
import logging
import re
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from src.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_client = httpx.Client(
    follow_redirects=True,
    timeout=settings.request_timeout,
    headers={"User-Agent": USER_AGENT},
)


def fetch_article_text(url: str) -> str:
    """Download the page at *url* and return the main readable text.

    Tries trafilatura first, then falls back to a naive BeautifulSoup
    text extraction. For daily.dev post/redirect URLs, extracts the
    article summary or follows the external article link from the
    server-rendered Next.js payload. Raises on network/parsing errors.
    """
    try:
        response = _client.get(url)
        response.raise_for_status()
        html = response.text
        final_url = str(response.url)
    except httpx.HTTPError as exc:
        logger.exception("Network error fetching %s", url)
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc

    if _is_daily_dev_url(final_url):
        daily_dev_text = _extract_from_daily_dev(html)
        if daily_dev_text:
            return _clean_text(daily_dev_text[: settings.max_article_length])

    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        deduplicate=True,
        target_language="en",
    )
    if text:
        return _clean_text(text[: settings.max_article_length])

    # Fallback: naive extraction
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return _clean_text(text[: settings.max_article_length])


def _is_daily_dev_url(url: str) -> bool:
    """Return True if *url* is hosted on daily.dev."""
    try:
        return "daily.dev" in urlparse(url).netloc
    except Exception:
        return False


def _extract_from_daily_dev(html: str) -> str | None:
    """Parse daily.dev's __NEXT_DATA__ payload for the article summary or text."""
    soup = BeautifulSoup(html, "lxml")
    next_data_script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not next_data_script or not next_data_script.string:
        return None

    try:
        data = json.loads(next_data_script.string)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse daily.dev __NEXT_DATA__: %s", exc)
        return None

    try:
        post = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialData", {})
            .get("post", {})
        )
        # The shared post contains the actual article metadata.
        shared_post = post.get("sharedPost") or post

        # Try to fetch the full external article first; fall back to summary.
        external_permalink = shared_post.get("permalink")
        if external_permalink:
            try:
                external_text = _fetch_external_text(external_permalink)
                if external_text:
                    return external_text
            except Exception as exc:
                logger.warning("Failed to fetch external daily.dev article: %s", exc)

        summary = shared_post.get("summary") or post.get("summary")
        if isinstance(summary, str):
            return summary

        return None
    except Exception as exc:
        logger.warning("Unexpected daily.dev payload structure: %s", exc)
        return None


def _fetch_external_text(url: str) -> str | None:
    """Fetch and extract readable text from an external article URL."""
    response = _client.get(url)
    response.raise_for_status()

    text = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=False,
        deduplicate=True,
        target_language="en",
    )
    if text:
        return _clean_text(text[: settings.max_article_length])

    # Fallback: naive extraction
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return _clean_text(text[: settings.max_article_length]) if text else None


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
