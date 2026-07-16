"""Parser for daily.dev emails from informer@daily.dev."""

import logging
import re
from typing import List

from bs4 import BeautifulSoup, Tag
from imap_tools import MailMessage

from src.models import Article
from src.parsers.base import EmailParser

logger = logging.getLogger(__name__)

READ_ARTICLE_PATTERN = re.compile(r"read\s*article\s*[→\>\-]*", re.IGNORECASE)
BLOCK_TAGS = {"div", "td", "section", "article", "tr", "table"}


class DailyDevParser(EmailParser):
    """Parses daily.dev digest emails to extract author, header, and article links."""

    name = "daily_dev"
    sender = "informer@daily.dev"

    def can_parse(self, email: MailMessage) -> bool:
        return email.from_ == self.sender

    def parse(self, email: MailMessage) -> list[Article]:
        if email.html:
            try:
                return self._parse_html(email.html)
            except Exception:
                logger.exception("HTML parsing failed, trying plain text fallback")
                if email.text:
                    return self._parse_text(email.text)
                return []
        if email.text:
            return self._parse_text(email.text)
        return []

    def _parse_html(self, html: str) -> list[Article]:
        soup = BeautifulSoup(html, "lxml")
        read_links = self._find_read_article_links(soup)
        if not read_links:
            logger.warning("No 'Read article' links found in HTML email")
            return []

        articles: list[Article] = []
        seen_links = set()
        for link in read_links:
            href = link.get("href", "")
            if not isinstance(href, str) or not href or href in seen_links:
                continue
            seen_links.add(href)

            container = self._find_article_container(link)
            author, header = self._extract_author_and_header(container, link)
            articles.append(Article(author=author, header=header, article_link=href))

        return articles

    def _find_read_article_links(self, soup: BeautifulSoup) -> List[Tag]:
        matches = []
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            if READ_ARTICLE_PATTERN.search(text):
                matches.append(a)
        return matches

    def _find_article_container(self, link: Tag) -> Tag | None:
        # Prefer the nearest table ancestor that contains a heading, the read link,
        # and a short author-like text. Daily.dev wraps each article in nested
        # tables; the author lives in a preceding row of the outer article table.
        for ancestor in link.parents:
            if not isinstance(ancestor, Tag):
                continue
            if ancestor.name == "table":
                has_heading = bool(ancestor.find(["h1", "h2", "h3", "h4", "h5"]))
                if not has_heading or link not in ancestor.descendants:
                    continue
                for elem in ancestor.find_all(["a", "p", "span"]):
                    text = elem.get_text(strip=True)
                    if not text or READ_ARTICLE_PATTERN.search(text):
                        continue
                    if 0 < len(text) <= 40:
                        return ancestor
        # Fallback to the original heuristic if the table-based search fails.
        for level in range(1, 7):
            fallback: Tag | None = link
            for _ in range(level):
                if fallback is None:
                    break
                fallback = fallback.parent
                if not isinstance(fallback, Tag):
                    fallback = None
                    break
            if fallback is None or not isinstance(fallback, Tag):
                continue
            if fallback.name not in BLOCK_TAGS:
                continue
            text = fallback.get_text(strip=True)
            links = fallback.find_all("a")
            if len(text) > 40 and len(links) <= 5:
                return fallback
        return link.parent if isinstance(link.parent, Tag) else None

    def _extract_author_and_header(
        self, container: Tag | None, read_link: Tag
    ) -> tuple[str, str]:
        if container is None:
            return "daily.dev", "Untitled"

        read_text = read_link.get_text(strip=True)

        # Find the header from headings.
        headings = container.find_all(["h1", "h2", "h3", "h4", "h5"])
        header = ""
        header_elem = None
        for h in headings:
            text = h.get_text(strip=True)
            if text and text != read_text and len(text) > 10:
                header = text
                header_elem = h
                break

        # Find the author as the short text that appears before the header.
        author = ""
        if header_elem:
            candidates = list(
                container.find_all(["a", "p", "span", "h1", "h2", "h3", "h4", "h5"])
            )
            try:
                ref_index = next(i for i, elem in enumerate(candidates) if elem is header_elem)
            except StopIteration:
                ref_index = None

            if ref_index is not None:
                for prev_elem in reversed(candidates[:ref_index]):
                    text = prev_elem.get_text(strip=True)
                    if not text or READ_ARTICLE_PATTERN.search(text):
                        continue
                    if 0 < len(text) <= 40:
                        author = text
                        break

        # If no author found from preceding text, try another heading as author.
        if not author:
            for h in headings:
                h_text = h.get_text(strip=True)
                if (
                    h_text
                    and h_text != header
                    and not READ_ARTICLE_PATTERN.search(h_text)
                    and len(h_text) <= 40
                ):
                    author = h_text
                    break

        # Fallback: scan all links in the container.
        if not author and not header:
            for a in container.find_all("a"):
                if a is read_link:
                    continue
                text = a.get_text(strip=True)
                if not text or READ_ARTICLE_PATTERN.search(text):
                    continue
                if len(text) <= 40:
                    author = text
                    break
                if not header and len(text) > 10:
                    header = text

        if not header:
            for elem in container.find_all(string=True):
                if elem.parent and elem.parent.name in {"script", "style", "noscript"}:
                    continue
                text = str(elem).strip()
                if text and len(text) > 10 and not READ_ARTICLE_PATTERN.search(text):
                    header = text
                    break

        if not header:
            header = "Untitled"
        if not author:
            author = "daily.dev"

        return author, header

    def _parse_text(self, text: str) -> list[Article]:
        pattern = re.compile(r"Read article\s*[→\>\-]*\s*(https?://\S+)", re.IGNORECASE)
        articles: list[Article] = []
        seen_links = set()
        for match in pattern.finditer(text):
            url = match.group(1)
            if url in seen_links:
                continue
            seen_links.add(url)

            preceding = text[: match.start()]
            lines = [line.strip() for line in preceding.splitlines() if line.strip()]
            author = ""
            header = ""
            for line in reversed(lines[-20:]):
                if not author and 0 < len(line) <= 40:
                    author = line
                elif not header and len(line) > 10:
                    header = line
            if not header:
                header = "Untitled"
            if not author:
                author = "daily.dev"

            articles.append(Article(author=author, header=header, article_link=url))

        return articles
