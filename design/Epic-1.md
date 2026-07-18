# Epic 1 — Platform Modernization: Streamable HTTP, Dependency Refresh, Python 3.13

## 1. Context and problem

The MCP server currently exposes only a **legacy SSE** transport at `/sse`
(`mcp.mount_sse()` in `src/main.py`). Modern MCP hosts such as **Codex** support only
**STDIO** and **Streamable HTTP** transports: Codex sends the `initialize` JSON-RPC
request as an HTTP `POST` to the configured URL, and the SSE endpoint answers
`405 Method Not Allowed`, making the server unusable there.

At the same time the dependency stack sits on old floors (`fastapi-mcp>=0.1.0`,
`trafilatura>=1.12.0`, `lxml>=4.9.0`, Python `>=3.10`) and carries unused packages
(`python-dotenv` — `pydantic-settings` already reads `.env` natively).

## 2. Goals

1. Serve MCP over **Streamable HTTP** at `/mcp` so Codex (and other modern clients)
   can connect; drop the legacy SSE endpoint entirely.
2. Raise all dependency floors to current releases and remove unused packages.
3. Replace `requests` with `httpx` for a single modern HTTP stack
   (fastapi-mcp already depends on httpx).
4. Move the Python baseline to **3.13** and slim the Docker image.

## 3. Key decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport | Replace `/sse` with `/mcp` via `mount_http()` | fastapi-mcp >=0.4.0 natively implements the Streamable HTTP spec; Codex requires it |
| Auth model | Unchanged | fastapi-mcp forwards the `Authorization` header into tool calls by default (`headers=["authorization"]`), so `Depends(verify_mcp_token)` protects tools identically on the new transport |
| HTTP client | `httpx` (sync `Client`) | One HTTP library across the project; drop `requests` + `types-requests` |
| Python floor | `>=3.13` | Current stable; wheels available for all deps |
| Versioning | Raised `>=` floors | Stay installable with future patches without exact-pin upkeep |
| Docker | `python:3.13-slim`, no apt build layer | lxml 6 / trafilatura 2.1 ship manylinux wheels (re-add layer only if build fails) |
| `python-dotenv` | Remove | Unused — `SettingsConfigDict(env_file=".env")` covers it |

## 4. Dependency floor changes (`pyproject.toml`)

| Package | Old floor | New floor |
|---------|-----------|-----------|
| fastapi | >=0.111.0 | >=0.139.0 |
| uvicorn[standard] | >=0.30.0 | >=0.51.0 |
| fastapi-mcp | >=0.1.0 | >=0.4.0 |
| imap-tools | >=1.6.0 | >=1.13.0 |
| trafilatura | >=1.12.0 | >=2.1.0 |
| beautifulsoup4 | >=4.12.0 | >=4.15.0 |
| pydantic-settings | >=2.0.0 | >=2.14.0 |
| lxml | >=4.9.0 | >=6.0.0 |
| lxml-html-clean | >=0.4.0 | >=0.4.5 |
| httpx | (dev only) | >=0.28.1 (main dep) |
| requests | >=2.32.0 | **removed** |
| python-dotenv | >=1.0.0 | **removed** |
| ruff | >=0.5.0 | >=0.15.0 |
| mypy | >=1.10.0 | >=2.3.0 |
| pytest | >=8.0.0 | >=9.1.0 |
| pytest-asyncio | >=0.23.0 | >=1.4.0 |
| types-requests | present | **removed** |

Compatibility notes:

- **trafilatura 2.x** breaking changes (`bare_extraction` return type, GUI removal,
  `fetch_url(decode=)` removal) do not affect this project — only `extract()` with
  `include_comments/include_tables/deduplicate/target_language` is used, unchanged in 2.x.
- **mypy 2.x** strict mode may surface new diagnostics; fix them or temporarily pin
  `mypy<2` as a fallback.
- **fastapi 0.139.x** compatibility with fastapi-mcp 0.4.0 must be verified by the test
  suite; if breakage appears, cap fastapi accordingly.

## 5. Story breakdown

### Story 1.1 — Upgrade dependency floors and remove unused packages

Scope: `pyproject.toml` only. Apply the floor table above **except** the
`requests`/`types-requests` removal and `httpx` promotion (owned by Story 1.3).
Remove `python-dotenv`. Set `requires-python`, ruff `target-version`, and mypy
`python_version` per Story 1.4 coordination (or land together).

### Story 1.2 — Migrate MCP transport from SSE to Streamable HTTP

Scope: `src/main.py` (`mcp.mount_sse()` → `mcp.mount_http()`), README (transport
description, new Codex `config.toml` section, LibreChat `type: streamable-http` YAML,
`/mcp` UAT smoke step), CODEBASE_MAP (transport row, module map, data-flow diagram),
`build.ipynb` (replace the `GET /sse` smoke cell with `POST /mcp` initialize).

Codex configuration to document:

```toml
[mcp_servers.news-agent]
url = "http://localhost:8000/mcp"
bearer_token_env_var = "MCP_API_TOKEN"
```

### Story 1.3 — Migrate article scraper from requests to httpx

Scope: `src/article_scraper.py` (shared `httpx.Client` with `follow_redirects=True`,
`timeout=settings.request_timeout`, User-Agent header; `requests.RequestException` →
`httpx.HTTPError`), `tests/test_article_scraper.py` (re-point mocks from `requests`
to the httpx client), `pyproject.toml` (remove `requests` + `types-requests`, add
`httpx>=0.28.1` to main deps), CODEBASE_MAP scraper row.

### Story 1.4 — Python 3.13 baseline and slim Docker image

Scope: `pyproject.toml` (`requires-python = ">=3.13"`, ruff `target-version = "py313"`,
mypy `python_version = "3.13"`), `Dockerfile` (`python:3.13-slim`, drop
`build-essential libxml2-dev libxslt1-dev` apt layer), README requirements section.

## 6. Verification strategy

1. Recreate `.venv` on Python 3.13 → `.venv\Scripts\pip install -e ".[dev]"`.
2. `.venv\Scripts\ruff check src` and `.venv\Scripts\mypy src` — clean.
3. `.venv\Scripts\pytest` — full suite green (scraper tests updated for httpx).
4. Start the server; `POST /mcp` with a JSON-RPC `initialize` body and Bearer token
   returns 200 with server info; unauthenticated tool calls still return 401;
   `GET /sse` no longer exists.
5. `docker compose up --build` — image builds without the apt layer and `/health`
   responds.

## 7. References

- fastapi-mcp v0.4.0 changelog (Streamable HTTP / `mount_http()`):
  https://github.com/tadata-org/fastapi_mcp/blob/main/CHANGELOG.md
- Codex MCP configuration (STDIO + Streamable HTTP only):
  https://learn.chatgpt.com/docs/extend/mcp
