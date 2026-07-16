"""Bearer token authentication for the MCP endpoints."""

from fastapi import Header, HTTPException, status

from src.config import settings


async def verify_mcp_token(authorization: str | None = Header(default=None)) -> None:
    """Verify that the incoming request carries the configured MCP Bearer token.

    The token is compared against the `MCP_API_TOKEN` environment variable.
    """
    expected = f"Bearer {settings.mcp_api_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing MCP API token",
        )
