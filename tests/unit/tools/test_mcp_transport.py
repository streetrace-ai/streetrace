"""Tests for MCP transport configuration classes."""

import pytest

from streetrace.tools.mcp_transport import (
    HttpTransport,
    SseTransport,
    StdioTransport,
    parse_transport_config,
)


class TestStdioTransport:
    """Test StdioTransport."""

    def test_creation_minimal(self) -> None:
        """Test creating minimal STDIO config."""
        config = StdioTransport(command="npx", args=["my-server"])

        assert config.command == "npx"
        assert config.args == ["my-server"]
        assert config.cwd is None
        assert config.env is None

    def test_creation_full(self) -> None:
        """Test creating full STDIO config."""
        config = StdioTransport(
            command="python",
            args=["-m", "my_server"],
            cwd="/tmp",  # noqa: S108
            env={"API_KEY": "secret"},
        )

        assert config.command == "python"
        assert config.args == ["-m", "my_server"]
        assert config.cwd == "/tmp"  # noqa: S108
        assert config.env == {"API_KEY": "secret"}


class TestHttpTransport:
    """Test HttpTransport."""

    def test_creation_minimal(self) -> None:
        """Test creating minimal HTTP config."""
        config = HttpTransport(url="http://localhost:8000/mcp")

        assert config.url == "http://localhost:8000/mcp"
        assert config.headers is None
        assert config.timeout is None

    def test_creation_full(self) -> None:
        """Test creating full HTTP config."""
        config = HttpTransport(
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer token"},
            timeout=30.0,
        )

        assert config.url == "https://api.example.com/mcp"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 30.0


class TestSseTransport:
    """Test SseTransport."""

    def test_creation_minimal(self) -> None:
        """Test creating minimal SSE config."""
        config = SseTransport(url="http://localhost:8000/sse")

        assert config.url == "http://localhost:8000/sse"
        assert config.headers is None
        assert config.timeout is None

    def test_creation_full(self) -> None:
        """Test creating full SSE config."""
        config = SseTransport(
            url="https://api.example.com/sse",
            headers={"Authorization": "Bearer token"},
            timeout=60.0,
        )

        assert config.url == "https://api.example.com/sse"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 60.0


class TestParseConnectionConfig:
    """Test parse_transport_config function."""

    def test_parse_stdio_minimal(self) -> None:
        """Test parsing minimal STDIO config."""
        data = {"type": "stdio", "command": "npx", "args": ["my-server"]}
        config = parse_transport_config(data)

        assert isinstance(config, StdioTransport)
        assert config.command == "npx"
        assert config.args == ["my-server"]
        assert config.cwd is None
        assert config.env is None

    def test_parse_stdio_full(self) -> None:
        """Test parsing full STDIO config."""
        data = {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "server"],
            "cwd": "/tmp",  # noqa: S108
            "env": {"KEY": "value"},
        }
        config = parse_transport_config(data)

        assert isinstance(config, StdioTransport)
        assert config.command == "python"
        assert config.args == ["-m", "server"]
        assert config.cwd == "/tmp"  # noqa: S108
        assert config.env == {"KEY": "value"}

    def test_parse_stdio_default_type(self) -> None:
        """Test parsing STDIO config with default type."""
        data = {"command": "npx", "args": ["my-server"]}
        config = parse_transport_config(data)

        assert isinstance(config, StdioTransport)
        assert config.command == "npx"
        assert config.args == ["my-server"]

    def test_parse_stdio_missing_command(self) -> None:
        """Test parsing STDIO config without command raises error."""
        data = {"type": "stdio", "args": ["my-server"]}

        with pytest.raises(
            ValueError,
            match="\ncommand\n  Field required",
        ):
            parse_transport_config(data)

    def test_parse_http_minimal(self) -> None:
        """Test parsing minimal HTTP config."""
        data = {"type": "http", "url": "http://localhost:8000/mcp"}
        config = parse_transport_config(data)

        assert isinstance(config, HttpTransport)
        assert config.url == "http://localhost:8000/mcp"
        assert config.headers is None
        assert config.timeout is None

    def test_parse_http_full(self) -> None:
        """Test parsing full HTTP config."""
        data = {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30.0,
        }
        config = parse_transport_config(data)

        assert isinstance(config, HttpTransport)
        assert config.url == "https://api.example.com/mcp"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 30.0

    def test_parse_http_missing_url(self) -> None:
        """Test parsing HTTP config without URL raises error."""
        data = {"type": "http", "headers": {"Auth": "token"}}

        with pytest.raises(ValueError, match="\nurl\n  Field required"):
            parse_transport_config(data)

    def test_parse_sse_minimal(self) -> None:
        """Test parsing minimal SSE config."""
        data = {"type": "sse", "url": "http://localhost:8000/sse"}
        config = parse_transport_config(data)

        assert isinstance(config, SseTransport)
        assert config.url == "http://localhost:8000/sse"
        assert config.headers is None
        assert config.timeout is None

    def test_parse_sse_full(self) -> None:
        """Test parsing full SSE config."""
        data = {
            "type": "sse",
            "url": "https://api.example.com/sse",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60.0,
        }
        config = parse_transport_config(data)

        assert isinstance(config, SseTransport)
        assert config.url == "https://api.example.com/sse"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 60.0

    def test_parse_sse_missing_url(self) -> None:
        """Test parsing SSE config without URL raises error."""
        data = {"type": "sse", "headers": {"Auth": "token"}}

        with pytest.raises(ValueError, match="\nurl\n  Field required"):
            parse_transport_config(data)

    def test_parse_unknown_type(self) -> None:
        """Test parsing config with unknown type raises error."""
        data = {"type": "unknown", "url": "http://localhost:8000"}

        with pytest.raises(ValueError, match="Unknown transport type: unknown"):
            parse_transport_config(data)

    def test_parse_case_insensitive_type(self) -> None:
        """Test parsing config with case-insensitive type."""
        data = {"type": "http", "url": "http://localhost:8000/mcp"}
        config = parse_transport_config(data)

        assert isinstance(config, HttpTransport)
        assert config.url == "http://localhost:8000/mcp"
