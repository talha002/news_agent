# Daily.dev Email Reader MCP Server

A FastAPI-based MCP (Model Context Protocol) server that connects to Gmail, reads unread emails from `informer@daily.dev`, extracts article metadata (author, header, link), fetches each article's text, and returns the result as JSON.

## Features

- **Gmail IMAP + App Password** authentication.
- **Bearer token** protection on the MCP endpoints.
- **Streamable HTTP transport** (`/mcp`) for Codex, LibreChat, and other modern MCP clients.
- Three MCP tools:
  1. `list_daily_dev_emails` — list unread daily.dev emails.
  2. `read_daily_dev_articles` — read the latest unread email (or a specific UID), extract articles, fetch their text, and mark the email as read.
  3. `read_article_url` — fetch a single article URL directly.

## Requirements

- Python 3.13+
- Gmail account with **2FA enabled** and an **App Password**

## Installation

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
MCP_API_TOKEN=your-secret-mcp-token
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
IMAP_TIMEOUT=30
```

`IMAP_TIMEOUT` is the maximum time (seconds) the server will wait for a Gmail IMAP socket operation. Lower it (e.g. `10`) during local UAT to fail fast if the credentials or network are wrong.

### Gmail App Password

1. Enable **2-Step Verification** on your Google account.
2. Go to **Google Account → Security → App passwords**.
3. Generate an app password for **Mail**.
4. Copy the 16-character password into `GMAIL_APP_PASSWORD` (spaces are OK).

## Docker

Build and run with Docker Compose:

```bash
cp .env.example .env
# edit .env with your credentials
docker compose up --build -d
```

Or with Docker directly:

```bash
docker build -t news-agent .
docker run -d --name news-agent --env-file .env -p 8000:8000 news-agent
```

The server is available at `http://localhost:8000` and the MCP endpoint at `http://localhost:8000/mcp`.

## Running the server

```bash
.venv\Scripts\python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Or with auto-reload during development:

```bash
.venv\Scripts\python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The MCP Streamable HTTP endpoint is available at:

```
http://localhost:8000/mcp
```

## Local UAT

You can validate the server end-to-end on your local machine either with the provided notebook or manually.

### Option A: Automated UAT notebook

1. Install Jupyter in the project venv:

   ```bash
   .venv\Scripts\pip install ipykernel
   .venv\Scripts\python -m ipykernel install --user --name news_agent --display-name "Python (news_agent)"
   ```

2. Launch Jupyter:

   ```bash
   .venv\Scripts\jupyter notebook build.ipynb
   ```

3. Select the `Python (news_agent)` kernel and run all cells top-to-bottom.

The notebook (`build.ipynb`) covers:
- environment setup
- starting the Uvicorn server
- health check (`GET /health`)
- authentication failure/success checks
- listing unread daily.dev emails (`POST /list-daily-dev-emails`)
- reading articles from the latest unread email (`POST /read-daily-dev-articles`)
- fetching a single article URL (`POST /read-article-url`)
- Streamable HTTP transport smoke test (`POST /mcp` initialize)
- stopping the server

The notebook sets a 60-second request timeout on every call, and the server now applies both `IMAP_TIMEOUT` (default 30 s) to Gmail IMAP **and** an endpoint-level `asyncio.wait_for` so it returns a `504` error instead of hanging forever. If the Gmail-dependent steps still appear to hang, set `IMAP_TIMEOUT=10` in `.env`, **restart the server**, and retry.

### Option B: Manual UAT steps

**Important:** if you already started the server before this code change, kill that process and restart it so it picks up the new IMAP timeout settings.

1. Start the server:

   ```bash
   .venv\Scripts\python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

2. Health check (no auth required):

   ```bash
   curl --max-time 10 http://localhost:8000/health
   ```

   Expected: `{"status":"ok"}`

3. Verify missing auth returns 401:

   ```bash
   curl --max-time 10 -X POST http://localhost:8000/list-daily-dev-emails
   ```

   Expected: `401 Unauthorized`

4. List unread daily.dev emails:

   ```bash
   curl --max-time 60 -X POST http://localhost:8000/list-daily-dev-emails \
     -H "Authorization: Bearer $MCP_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"limit": 10}'
   ```

   The server will abort the IMAP call after `IMAP_TIMEOUT + 5` seconds (default 35 s) and return `504` if it cannot connect. If this still times out, the server cannot reach Gmail IMAP or the credentials in `.env` are wrong.

5. Read articles from the latest unread email:

   ```bash
   curl --max-time 60 -X POST http://localhost:8000/read-daily-dev-articles \
     -H "Authorization: Bearer $MCP_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"uid": null}'
   ```

   ⚠️ This step marks the processed email as read in Gmail.

6. Fetch a single article URL directly:

   ```bash
   curl --max-time 60 -X POST http://localhost:8000/read-article-url \
     -H "Authorization: Bearer $MCP_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://daily.dev/blog/getting-started-with-daily-dev"}'
   ```

7. Verify the MCP endpoint responds to a JSON-RPC `initialize` request:

   ```bash
   curl --max-time 10 -X POST http://localhost:8000/mcp \
     -H "Authorization: Bearer $MCP_API_TOKEN" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "initialize",
       "params": {
         "protocolVersion": "2025-03-26",
         "capabilities": {},
         "clientInfo": {"name": "curl-smoke", "version": "1.0.0"}
       }
     }'
   ```

   Expected: `200 OK` with a JSON-RPC result containing `protocolVersion`, `capabilities`, and `serverInfo`.

## Codex configuration

Codex supports STDIO and Streamable HTTP MCP transports. Add this to your
`~/.codex/config.toml`:

```toml
[mcp_servers.news-agent]
url = "http://localhost:8000/mcp"
bearer_token_env_var = "MCP_API_TOKEN"
```

Set the `MCP_API_TOKEN` environment variable to the same value as in `.env`, then
restart Codex. Codex POSTs the JSON-RPC `initialize` request to `/mcp`.

## LibreChat configuration

Add this to your `librechat.yaml`:

```yaml
mcpServers:
  daily-dev-reader:
    type: streamable-http
    url: http://your-server:8000/mcp
    headers:
      Authorization: Bearer ${MCP_API_TOKEN}
    initTimeout: 15000
    timeout: 60000
```

If LibreChat is running on the same machine, use `http://localhost:8000/mcp`.

## MCP tool usage

### `list_daily_dev_emails`

Request:

```json
{
  "name": "list_daily_dev_emails",
  "arguments": {
    "limit": 10
  }
}
```

Response:

```json
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
```

### `read_daily_dev_articles`

Request (latest unread email):

```json
{
  "name": "read_daily_dev_articles",
  "arguments": {
    "uid": null
  }
}
```

Response:

```json
{
  "email_subject": "Daily Digest: React, AI, and Cloud",
  "email_date": "2026-07-12T09:00:00Z",
  "email_from": "informer@daily.dev",
  "email_uid": "12345",
  "articles": [
    {
        "author": "Bobby Iliev",
      "header": "Next.js 15 is here",
      "article_link": "https://daily.dev/blog/...",
      "article_text": "Full extracted article text...",
      "error": null
    }
  ]
}
```

### `read_article_url`

Request:

```json
{
  "name": "read_article_url",
  "arguments": {
    "url": "https://daily.dev/blog/..."
  }
}
```

Response:

```json
{
  "article_link": "https://daily.dev/blog/...",
  "article_text": "Full extracted article text...",
  "error": null
}
```

## Development

Run the linter and type checker:

```bash
.venv\Scripts\ruff check src
.venv\Scripts\mypy src
```

## Project structure

```
news_agent/
├── .env                  # Local credentials (not committed)
├── .env.example          # Example configuration
├── .gitignore
├── pyproject.toml        # Dependencies and tool config
├── README.md
└── src/
    ├── __init__.py
    ├── main.py              # FastAPI app + MCP mount + tool endpoints
    ├── config.py            # Pydantic settings
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

## Adding a new email source

1. Create a new parser in `src/parsers/<source>.py` implementing `EmailParser`.
2. Add a new MCP endpoint in `src/main.py` that calls `read_email_articles(parser=YourParser(), uid=...)`.
3. No changes to `src/services/email_reader.py` or `src/imap_client.py` are needed.

Example:

```python
# src/parsers/tech_crunch.py
class TechCrunchParser(EmailParser):
    name = "tech_crunch"
    sender = "newsletters@techcrunch.com"
    ...

# src/main.py
@app.post("/read-techcrunch-articles", ...)
async def read_techcrunch_articles(request: ReadArticlesRequest) -> ArticlesResponse:
    return await read_email_articles(parser=TechCrunchParser(), uid=request.uid)
```

## Security notes

- Never commit `.env` or real credentials.
- Use HTTPS and a strong `MCP_API_TOKEN` in production.
- The MCP endpoint is protected by the Bearer token; LibreChat sends it in the `Authorization` header.
