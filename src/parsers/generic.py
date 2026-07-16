"""Generic fallback parser for unknown email sources."""

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from imap_tools import MailMessage

from src.models import Article
from src.parsers.base import EmailParser

logger = logging.getLogger(__name__)

ARTICLE_LINK_PATTERNS = [
    re.compile(r"read\s*article\s*[→\>\-]*", re.IGNORECASE),
    re.compile(r"read\s*more", re.IGNORECASE),
    re.compile(r"continue\s*reading", re.IGNORECASE),
]


class GenericParser(EmailParser):
    """Generic parser that extracts article-like links from any email.

    Useful as a fallback or starting point for new sources before writing
    a dedicated parser.
    """

    name = "generic"
    sender = "*"

    def can_parse(self, email: MailMessage) -> bool:
        return True

    def parse(self, email: MailMessage) -> list[Article]:
        if email.html:
            return self._parse_html(email.html)
        if email.text:
            return self._parse_text(email.text)
        return []

    def _parse_html(self, html: str) -> list[Article]:
        soup = BeautifulSoup(html, "lxml")
        articles: list[Article] = []
        seen = set()

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if not isinstance(href, str) or not href or href in seen:
                continue
            seen.add(href)

            text = a.get_text(strip=True)
            if not self._looks_like_article_link(text):
                continue

            title = self._infer_title(a)
            domain = self._domain_from_url(href)
            articles.append(
                Article(
                    author=domain,
                    header=title,
                    article_link=href,
                )
            )

        return articles

    def _parse_text(self, text: str) -> list[Article]:
        articles: list[Article] = []
        seen = set()
        # Find lines that look like article links followed by URLs
        for pattern in ARTICLE_LINK_PATTERNS:
            for match in pattern.finditer(text):
                url_match = re.search(r"https?://\S+", text[match.end() : match.end() + 500])
                if not url_match:
                    continue
                url = url_match.group(0)
                if url in seen:
                    continue
                seen.add(url)

                preceding = text[: match.start()]
                lines = [line.strip() for line in preceding.splitlines() if line.strip()]
                title = "Untitled"
                for line in reversed(lines[-10:]):
                    if len(line) > 10:
                        title = line
                        break

                domain = self._domain_from_url(url)
                articles.append(Article(author=domain, header=title, article_link=url))
        return articles

    def _looks_like_article_link(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in ARTICLE_LINK_PATTERNS)

    def _infer_title(self, link_tag: Tag) -> str:
        # Try title attribute, then parent heading, then link text itself
        title = link_tag.get("title", "")
        if isinstance(title, str) and title.strip():
            return title.strip()

        for parent in link_tag.parents:
            if isinstance(parent, Tag) and parent.name in {"h1", "h2", "h3", "h4"}:
                return str(parent.get_text(strip=True))

        text = link_tag.get_text(strip=True)
        # Remove CTA words to leave just the title if possible
        cleaned = re.sub(r"(?i)read\s*article|read\s*more|continue\s*reading|[→\>\-]", "", text)
        cleaned = cleaned.strip()
        return cleaned if cleaned else text

    def _domain_from_url(self, url: str) -> str:
        try:
            return str(urlparse(url).netloc) or "unknown"
        except Exception:
            logger.warning("Failed to parse URL domain: %s", url)
            return "unknown"
