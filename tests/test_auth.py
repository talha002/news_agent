"""Tests for src/auth.py."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException, status

from src.auth import verify_mcp_token


@pytest.mark.asyncio
async def test_verify_mcp_token_valid(mock_env_vars: dict[str, str]) -> None:
    """A valid Bearer token should pass without raising."""
    with patch.object(
        __import__("src.auth", fromlist=["settings"]).settings,
        "mcp_api_token",
        mock_env_vars["MCP_API_TOKEN"],
    ):
        await verify_mcp_token(f"Bearer {mock_env_vars['MCP_API_TOKEN']}")


@pytest.mark.asyncio
async def test_verify_mcp_token_missing() -> None:
    """Missing authorization header should raise 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_mcp_token(None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_mcp_token_wrong_format() -> None:
    """Tokens without the Bearer prefix should raise 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_mcp_token("wrong-token")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_mcp_token_invalid_bearer(mock_env_vars: dict[str, str]) -> None:
    """A Bearer token with the wrong value should raise 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_mcp_token("Bearer invalid-token")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
