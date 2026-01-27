"""Tests for DSL tool factory module."""

import os
from unittest.mock import patch

from streetrace.dsl.runtime.tool_factory import (
    _build_auth_header,
    _build_headers,
    _resolve_interpolation,
    create_builtin_tool_refs,
    create_mcp_tool_ref,
)
from streetrace.tools.mcp_transport import HttpTransport, SseTransport


class TestResolveInterpolation:
    """Tests for environment variable interpolation."""

    def test_simple_env_var(self) -> None:
        """Test resolving ${VAR} pattern."""
        with patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            result = _resolve_interpolation("${MY_TOKEN}")
            assert result == "secret123"

    def test_env_prefix_pattern(self) -> None:
        """Test resolving ${env:VAR} pattern."""
        with patch.dict(os.environ, {"API_KEY": "key456"}):
            result = _resolve_interpolation("${env:API_KEY}")
            assert result == "key456"

    def test_missing_env_var_returns_empty(self) -> None:
        """Test that missing env var returns empty string."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the var if it exists
            os.environ.pop("NONEXISTENT_VAR", None)
            result = _resolve_interpolation("${NONEXISTENT_VAR}")
            assert result == ""

    def test_no_interpolation_returns_unchanged(self) -> None:
        """Test that strings without interpolation are unchanged."""
        result = _resolve_interpolation("plain_token")
        assert result == "plain_token"

    def test_mixed_content(self) -> None:
        """Test string with interpolation mixed with literal text."""
        with patch.dict(os.environ, {"PREFIX": "Bearer"}):
            result = _resolve_interpolation("${PREFIX} token")
            assert result == "Bearer token"


class TestBuildAuthHeader:
    """Tests for building auth headers."""

    def test_bearer_auth(self) -> None:
        """Test bearer token auth header."""
        auth = {"type": "bearer", "value": "my_token"}
        result = _build_auth_header(auth)
        assert result == "Bearer my_token"

    def test_basic_auth(self) -> None:
        """Test basic auth header."""
        auth = {"type": "basic", "value": "dXNlcjpwYXNz"}
        result = _build_auth_header(auth)
        assert result == "Basic dXNlcjpwYXNz"

    def test_bearer_with_env_interpolation(self) -> None:
        """Test bearer auth with environment variable."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_secret"}):
            auth = {"type": "bearer", "value": "${GITHUB_TOKEN}"}
            result = _build_auth_header(auth)
            assert result == "Bearer ghp_secret"

    def test_empty_value_returns_none(self) -> None:
        """Test that empty auth value returns None."""
        auth = {"type": "bearer", "value": ""}
        result = _build_auth_header(auth)
        assert result is None

    def test_unknown_auth_type_returns_none(self) -> None:
        """Test that unknown auth type returns None with warning."""
        auth = {"type": "oauth", "value": "token"}
        result = _build_auth_header(auth)
        assert result is None


class TestBuildHeaders:
    """Tests for building complete headers dict."""

    def test_auth_only(self) -> None:
        """Test building headers from auth only."""
        tool_def = {
            "auth": {"type": "bearer", "value": "token123"},
        }
        result = _build_headers(tool_def)
        assert result == {"Authorization": "Bearer token123"}

    def test_explicit_headers_only(self) -> None:
        """Test building headers from explicit headers only."""
        tool_def = {
            "headers": {"X-Custom": "value"},
        }
        result = _build_headers(tool_def)
        assert result == {"X-Custom": "value"}

    def test_auth_and_explicit_headers(self) -> None:
        """Test combining auth and explicit headers."""
        tool_def = {
            "auth": {"type": "bearer", "value": "token"},
            "headers": {"X-Custom": "value"},
        }
        result = _build_headers(tool_def)
        assert result == {
            "Authorization": "Bearer token",
            "X-Custom": "value",
        }

    def test_no_headers_returns_none(self) -> None:
        """Test that no headers returns None."""
        tool_def = {}
        result = _build_headers(tool_def)
        assert result is None


class TestCreateMcpToolRef:
    """Tests for creating MCP tool references."""

    def test_http_transport(self) -> None:
        """Test creating HTTP transport."""
        tool_def = {
            "url": "https://api.example.com/mcp",
            "auth": {"type": "bearer", "value": "token"},
        }
        result = create_mcp_tool_ref("example", tool_def)

        assert result.name == "example"
        assert result.tools == ["*"]
        assert isinstance(result.server, HttpTransport)
        assert result.server.url == "https://api.example.com/mcp"
        assert result.server.headers == {"Authorization": "Bearer token"}

    def test_sse_transport_by_url_suffix(self) -> None:
        """Test SSE transport detection by /sse suffix."""
        tool_def = {"url": "https://api.example.com/sse"}
        result = create_mcp_tool_ref("example", tool_def)

        assert isinstance(result.server, SseTransport)
        assert result.server.url == "https://api.example.com/sse"

    def test_sse_transport_by_url_pattern(self) -> None:
        """Test SSE transport detection by /sse in URL path."""
        tool_def = {"url": "https://api.example.com/sse/endpoint"}
        result = create_mcp_tool_ref("example", tool_def)

        assert isinstance(result.server, SseTransport)

    def test_github_copilot_example(self) -> None:
        """Test real-world GitHub Copilot MCP config."""
        with patch.dict(os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test123"}):
            tool_def = {
                "url": "https://api.githubcopilot.com/mcp/",
                "auth": {
                    "type": "bearer",
                    "value": "${GITHUB_PERSONAL_ACCESS_TOKEN}",
                },
            }
            result = create_mcp_tool_ref("github", tool_def)

            assert result.name == "github"
            assert isinstance(result.server, HttpTransport)
            assert result.server.url == "https://api.githubcopilot.com/mcp/"
            assert result.server.headers == {"Authorization": "Bearer ghp_test123"}


class TestCreateBuiltinToolRefs:
    """Tests for creating builtin tool references."""

    def test_fs_tool_by_name(self) -> None:
        """Test inferring fs tool from name."""
        result = create_builtin_tool_refs("fs", {})
        assert len(result) > 0
        assert all(ref.module == "fs_tool" for ref in result)

    def test_cli_tool_by_name(self) -> None:
        """Test inferring cli tool from name."""
        result = create_builtin_tool_refs("cli", {})
        assert len(result) > 0
        assert all(ref.module == "cli_tool" for ref in result)

    def test_fs_tool_by_builtin_ref(self) -> None:
        """Test fs tool via builtin_ref."""
        result = create_builtin_tool_refs("myfs", {"builtin_ref": "streetrace.fs"})
        assert len(result) > 0
        assert all(ref.module == "fs_tool" for ref in result)

    def test_unknown_tool_returns_empty(self) -> None:
        """Test that unknown tool returns empty list."""
        result = create_builtin_tool_refs("unknown", {})
        assert result == []
