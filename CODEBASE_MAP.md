# Daily.dev Email Reader — Code Base Map

## 1. Project overview

| Item | Value |
|------|-------|
| **Name** | `news-agent` |
| **Purpose** | MCP server that reads `informer@daily.dev` emails, extracts article links, fetches article text, and returns JSON. |
| **Framework** | FastAPI + `fastapi-mcp` |
| **Transport** | SSE at `/sse` |
| **Auth** | Gmail IMAP App Password + MCP Bearer token |
| **Email processing** | Marks emails as read after `read_daily_dev_articles` succeeds. |

## 2. File structure

```
news_agent/
├── .env                  # Local credentials (not committed)
├── .env.example          # Example configuration
├── .gitignore
├── pyproject.toml        # Dependencies, ruff, mypy config
├── README.md
└── src/
    ├── __init__.py
    ├── main.py              # FastAPI app + MCP mount + tool endpoints
    ├── config.py            # Pydantic settings (env vars)
    ├── auth.py              # Bearer token auth
    ├── imap_client.py       # Gmail IMAP client
    ├── article_scraper.py   # HTTP fetch + article text extraction
    ├── models.py            # Pydantic request/response models
    ├── parsers/             # Per-source email parsers
    │   ├── __init__.py
    │   ├── base.py          # Parser protocol
    │   ├── daily_dev.py     # Daily.dev parser
    │   └── generic.py       # Fallback generic parser
    └── services/            # Shared orchestration logic
        ├── __init__.py
        └── email_reader.py  # Fetch, parse, scrape, mark-read
```

## 3. Module map

### `src/config.py`

| Symbol | Type | Purpose |
|--------|------|---------|
| `Settings` | `BaseSettings` | Loads all env vars from `.env`. |
| `settings` | `Settings` | Singleton used everywhere. |

Key env vars:

- `GMAIL_EMAIL` (required)
- `GMAIL_APP_PASSWORD` (required)
- `MCP_API_TOKEN` (required)
- `HOST`, `PORT`, `LOG_LEVEL`
- `DAILY_DEV_SENDER` default `"informer@daily.dev"`
- `DEFAULT_EMAIL_LIMIT` default `10`
- `REQUEST_TIMEOUT` default `30` (HTTP timeout for article fetching)
- `MAX_ARTICLE_LENGTH` default `20000`
- `IMAP_TIMEOUT` default `30` (socket timeout for Gmail IMAP)

### `src/auth.py`

| Symbol | Type | Purpose |
|--------|------|---------|
| `verify_mcp_token` | `async def` | FastAPI dependency. Checks `Authorization: Bearer <MCP_API_TOKEN>` and raises `401` if invalid/missing. |

### `src/models.py`

| Model | Fields | Used by |
|-------|--------|---------|
| `EmailSummary` | `uid`, `subject`, `date`, `from_address`, `read` | `list_daily_dev_emails` |
| `Article` | `author`, `header`, `article_link`, `article_text`, `error` | All parsers and `read_email_articles` service |
| `ArticlesResponse` | `email_subject`, `email_date`, `email_from`, `email_uid`, `articles` | All source tools via `read_email_articles` service |
| `ReadArticlesRequest` | `uid: str \| None` | All source tools via `read_email_articles` service |
| `ReadUrlRequest` | `url: HttpUrl` | `read_article_url` |
| `ReadUrlResponse` | `article_link`, `article_text`, `error` | `read_article_url` |

### `src/imap_client.py`

| Function | Purpose |
|----------|---------|
| `_get_mailbox()` | Login to Gmail IMAP (`imap.gmail.com:993`) using `IMAP_TIMEOUT`. |
| `get_daily_dev_emails(limit=10)` | Fetch unread daily.dev emails. |
| `get_unread_emails_from_sender(sender, limit=10)` | Generic fetch for any sender. |
| `get_latest_unread_email_from_sender(sender)` | Returns the single latest unread email from *sender*. |
| `get_email_by_uid(uid)` | Fetch a single email by UID without marking it seen. |
| `mark_email_as_read(uid)` | Set `\Seen` flag on the email. |
| `is_email_read(email)` | Check if `\Seen` is present. |

### `src/parsers/base.py`

| Symbol | Type | Purpose |
|--------|------|---------|
| `EmailParser` | `Protocol` | Every parser must implement `name`, `sender`, `can_parse()`, and `parse()`. |

#### Parser contract

Each parser must provide:

```python
name: str                # Unique identifier, e.g. "daily_dev"
sender: str              # IMAP FROM address to match, e.g. "informer@daily.dev"

def can_parse(self, email: MailMessage) -> bool: ...
def parse(self, email: MailMessage) -> list[Article]: ...
```

`can_parse()` is used by `read_email_articles()` when a UID is provided, to validate the fetched email belongs to the parser.
`parse()` returns the list of `Article` objects extracted from the email body.

### `src/parsers/daily_dev.py`

| Class | Purpose |
|-------|---------|
| `DailyDevParser` | Parses `informer@daily.dev` emails. Extracts author, header, and article link from each "Read article" section. |

### `src/parsers/generic.py`

| Class | Purpose |
|-------|---------|
| `GenericParser` | Fallback parser that extracts article-like links from any email. Useful as a starting point for new sources. |

### `src/services/email_reader.py`

| Function | Purpose |
|----------|---------|
| `read_email_articles(parser, uid=None)` | Shared orchestration: fetch email by sender/UID, parse with *parser*, scrape article text, mark read, return `ArticlesResponse`. |
| `_fetch_email(parser, uid=None)` | Resolve the `MailMessage` either by UID (with parser validation) or latest unread from `parser.sender`. |

### `src/article_scraper.py`

| Function | Purpose |
|----------|---------|
| `fetch_article_text(url)` | `requests.get` the URL, then extract main text with `trafilatura`; falls back to BeautifulSoup naive extraction. |
| `_clean_text(text)` | Normalize whitespace. |

### `src/main.py`

| Endpoint | Path | MCP Tool Name | Purpose |
|----------|------|---------------|---------|
| `health` | `GET /health` | (excluded) | Health check. |
| `list_daily_dev_emails` | `POST /list-daily-dev-emails` | `list_daily_dev_emails` | List unread emails. |
| `read_daily_dev_articles` | `POST /read-daily-dev-articles` | `read_daily_dev_articles` | Parse email + fetch articles + mark read. |
| `read_article_url` | `POST /read-article-url` | `read_article_url` | Fetch any article URL directly. |

Other key items:

- `mcp = FastApiMCP(app)` — creates MCP server from FastAPI app.
- `mcp.mount_sse()` — mounts SSE transport at `/sse`.

## 4. Data flow

```
LibreChat ──SSE──▶ /sse
                     │
                     ▼
         FastAPI-MCP routes tool call to endpoint
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
 /list-daily-dev  /read-daily-dev   /read-article-url
 /emails          /articles
    │                │                │
    ▼                ▼                ▼
get_daily_dev    read_email_       fetch_article_text
_emails          articles(DailyDevParser)
                     │
                     ▼
       get_latest_unread_email_from_sender
                     │
                     ▼
            DailyDevParser.parse()
                     │
                     ▼
            fetch_article_text (per link)
                     │
                     ▼
            mark_email_as_read
                     │
                     ▼
            JSON response to LibreChat
```

## 5. Configuration

Create `.env` from `.env.example`:

```env
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
MCP_API_TOKEN=your-secret-token
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

## 6. Run commands

```bash
# Install
.venv\Scripts\pip install -e ".[dev]"

# Lint / type check
.venv\Scripts\ruff check src
.venv\Scripts\mypy src

# Run server
.venv\Scripts\python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## 7. Adding a new email source

1. Create `src/parsers/<source>.py` implementing `EmailParser`.
2. Add a new endpoint in `src/main.py`:

```python
from src.parsers.tech_crunch import TechCrunchParser

@app.post("/read-techcrunch-articles", ...)
async def read_techcrunch_articles(request: ReadArticlesRequest) -> ArticlesResponse:
    return await read_email_articles(parser=TechCrunchParser(), uid=request.uid)
```

No changes to `src/services/email_reader.py` or `src/imap_client.py` are needed.
