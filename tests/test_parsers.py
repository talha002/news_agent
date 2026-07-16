"""Tests for src/parsers/*."""

from typing import Any

from src.parsers.daily_dev import DailyDevParser
from src.parsers.generic import GenericParser

DAILY_DIGEST_HTML = """
<html>
<body>
  <table>
    <tr>
      <td>
        <h2>Vercel</h2>
        <p>Next.js 15 is here with exciting features.</p>
        <a href="https://daily.dev/blog/next-js-15">Read article →</a>
      </td>
    </tr>
    <tr>
      <td>
        <h2>Stripe</h2>
        <p>New payments API released today with lots of details.</p>
        <a href="https://daily.dev/blog/stripe-api">Read article</a>
      </td>
    </tr>
  </table>
</body>
</html>
"""

DAILY_DIGEST_HTML_AUTHOR_IN_LINK = """
<html>
<body>
  <table class="es-content" align="center" cellspacing="0" cellpadding="0" role="none">
    <tr>
      <td>
        <table
          class="es-content-body"
          align="center"
          cellpadding="0"
          cellspacing="0"
          bgcolor="#ffffff"
          role="none"
        >
          <tr>
            <td>
              <table cellpadding="0" cellspacing="0" role="none">
                <tr>
                  <td>
                    <p>
                      <a href="https://daily.dev/posts/pzbiK3Lbx">iO tech_hub</a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td>
              <table cellpadding="0" cellspacing="0" role="none">
                <tr>
                  <td>
                    <h5>
                      <a href="https://daily.dev/posts/pzbiK3Lbx">
                        Front-End Architecture with Domain-Driven Design
                      </a>
                    </h5>
                    <span class="es-button-border">
                      <a
                        href="https://daily.dev/posts/pzbiK3Lbx"
                        class="es-button"
                      >
                        Read article →
                      </a>
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class TestDailyDevParser:
    def test_can_parse_matching_sender(self, make_mail_message: Any) -> None:
        email = make_mail_message(from_address="informer@daily.dev")
        assert DailyDevParser().can_parse(email) is True

    def test_can_parse_wrong_sender(self, make_mail_message: Any) -> None:
        email = make_mail_message(from_address="other@example.com")
        assert DailyDevParser().can_parse(email) is False

    def test_parse_html(self, make_mail_message: Any) -> None:
        email = make_mail_message(html=DAILY_DIGEST_HTML, text=None)
        articles = DailyDevParser().parse(email)
        assert len(articles) == 2
        assert articles[0].author == "Vercel"
        assert "Next.js" in articles[0].header
        assert str(articles[0].article_link) == "https://daily.dev/blog/next-js-15"
        assert articles[1].author == "Stripe"

    def test_parse_html_author_in_link(self, make_mail_message: Any) -> None:
        email = make_mail_message(html=DAILY_DIGEST_HTML_AUTHOR_IN_LINK, text=None)
        articles = DailyDevParser().parse(email)
        assert len(articles) == 1
        assert articles[0].author == "iO tech_hub"
        assert articles[0].header == "Front-End Architecture with Domain-Driven Design"
        assert str(articles[0].article_link) == "https://daily.dev/posts/pzbiK3Lbx"

    def test_parse_text(self, make_mail_message: Any) -> None:
        text = """
Next.js 15 is here with a really long description
Vercel
Read article → https://daily.dev/blog/next-js-15

New payments API released today with lots of details
Stripe
Read article https://daily.dev/blog/stripe-api
"""
        email = make_mail_message(html=None, text=text)
        articles = DailyDevParser().parse(email)
        assert len(articles) == 2
        assert articles[0].author == "Vercel"
        assert "Next.js" in articles[0].header
        assert str(articles[0].article_link) == "https://daily.dev/blog/next-js-15"

    def test_parse_empty_email(self, make_mail_message: Any) -> None:
        email = make_mail_message(html=None, text=None)
        articles = DailyDevParser().parse(email)
        assert articles == []


class TestGenericParser:
    def test_can_parse_any_sender(self, make_mail_message: Any) -> None:
        email = make_mail_message(from_address="random@newsletter.com")
        assert GenericParser().can_parse(email) is True

    def test_parse_html_article_link(self, make_mail_message: Any) -> None:
        html = """
<html>
<body>
  <h2>Breaking News</h2>
  <a href="https://example.com/news" title="Read more">Read more</a>
</body>
</html>
"""
        email = make_mail_message(html=html, text=None)
        articles = GenericParser().parse(email)
        assert len(articles) == 1
        assert articles[0].author == "example.com"
        assert articles[0].header == "Read more"
        assert str(articles[0].article_link) == "https://example.com/news"

    def test_parse_text_article_link(self, make_mail_message: Any) -> None:
        text = """
Latest Update
Read more https://example.com/update
"""
        email = make_mail_message(html=None, text=text)
        articles = GenericParser().parse(email)
        assert len(articles) == 1
        assert articles[0].author == "example.com"
        assert articles[0].header == "Latest Update"

    def test_domain_from_url_invalid(self) -> None:
        parser = GenericParser()
        assert parser._domain_from_url("://not-a-url") == "unknown"
