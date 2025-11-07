"""Tests for agent resolver."""

from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from streetrace.agents.base_agent_loader import AgentInfo
from streetrace.agents.resolver import SourceResolution, SourceResolver, SourceType


@pytest.fixture
def sample_yaml_content() -> str:
    """Sample YAML content for testing."""
    return """version: 1
kind: agent
name: TestAgent
description: A test agent
"""


@pytest.fixture
def temp_agent_file(tmp_path: Path, sample_yaml_content: str) -> Path:
    """Create a temporary agent file."""
    agent_file = tmp_path / "test_agent.yaml"
    agent_file.write_text(sample_yaml_content)
    return agent_file


@pytest.fixture
def discovered_agents(temp_agent_file: Path) -> list[AgentInfo]:
    """Create a list of discovered agents."""
    return [
        AgentInfo(
            name="TestAgent",
            description="A test agent",
            file_path=temp_agent_file,
        ),
    ]


class TestSourceResolver:
    """Test suite for SourceResolver."""

    def test_resolve_http_url(self, sample_yaml_content: str) -> None:
        """Test resolving an HTTP URL."""
        resolver = SourceResolver(http_auth="Bearer token123")

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = sample_yaml_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent.yaml")

            assert result.content == sample_yaml_content
            assert result.source == "https://example.com/agent.yaml"
            assert result.source_type == SourceType.HTTP_URL
            assert result.file_path is None

            # Verify headers were set correctly
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
            assert "Accept" in call_kwargs["headers"]

    def test_resolve_http_url_without_auth(self, sample_yaml_content: str) -> None:
        """Test resolving an HTTP URL without authentication."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = sample_yaml_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent.yaml")

            assert result.content == sample_yaml_content
            # Verify Authorization header is not set
            call_kwargs = mock_get.call_args[1]
            assert "Authorization" not in call_kwargs["headers"]

    def test_resolve_http_url_failure(self) -> None:
        """Test HTTP URL resolution failure."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(ValueError, match="Failed to fetch content"):
                resolver.resolve("https://example.com/agent.yaml")

    def test_resolve_absolute_path(
        self,
        temp_agent_file: Path,
        sample_yaml_content: str,
    ) -> None:
        """Test resolving an absolute file path."""
        resolver = SourceResolver()

        result = resolver.resolve(str(temp_agent_file))

        assert result.content == sample_yaml_content
        assert result.source == str(temp_agent_file)
        assert result.source_type == SourceType.FILE_PATH
        assert result.file_path == temp_agent_file

    def test_resolve_home_directory_path(
        self,
        tmp_path: Path,
        sample_yaml_content: str,
    ) -> None:
        """Test resolving a path with ~/ prefix."""
        resolver = SourceResolver()

        # Create a file in a temp location
        agent_file = tmp_path / "agent.yaml"
        agent_file.write_text(sample_yaml_content)

        # Mock expanduser to return our temp path
        with patch("pathlib.Path.expanduser") as mock_expand:
            mock_expand.return_value = agent_file

            result = resolver.resolve("~/agent.yaml")

            assert result.content == sample_yaml_content
            assert result.source_type == SourceType.FILE_PATH

    def test_resolve_relative_path(
        self,
        tmp_path: Path,
        sample_yaml_content: str,
    ) -> None:
        """Test resolving a relative file path."""
        resolver = SourceResolver()

        # Create a base file and a referenced file
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        agent_file = base_dir / "agent.yaml"
        agent_file.write_text(sample_yaml_content)

        result = resolver.resolve("agent.yaml", base_path=base_dir / "main.yaml")

        assert result.content == sample_yaml_content
        assert result.source_type == SourceType.FILE_PATH

    def test_resolve_discovered_agent_name(
        self,
        discovered_agents: list[AgentInfo],
        sample_yaml_content: str,
    ) -> None:
        """Test resolving by discovered agent name."""
        discovered_sources = {
            agent.name.lower(): agent.file_path
            for agent in discovered_agents
            if agent.file_path
        }
        resolver = SourceResolver(discovered_sources=discovered_sources)

        result = resolver.resolve("TestAgent")

        assert result.content == sample_yaml_content
        assert result.source_type == SourceType.FILE_PATH

    def test_resolve_discovered_agent_name_case_insensitive(
        self,
        discovered_agents: list[AgentInfo],
        sample_yaml_content: str,
    ) -> None:
        """Test resolving by discovered agent name is case-insensitive."""
        discovered_sources = {
            agent.name.lower(): agent.file_path
            for agent in discovered_agents
            if agent.file_path
        }
        resolver = SourceResolver(discovered_sources=discovered_sources)

        result = resolver.resolve("testagent")

        assert result.content == sample_yaml_content
        assert result.source_type == SourceType.FILE_PATH

    def test_resolve_not_found(self) -> None:
        """Test resolution failure when identifier cannot be resolved."""
        resolver = SourceResolver()

        with pytest.raises(ValueError, match="Could not resolve identifier"):
            resolver.resolve("nonexistent_agent")

    def test_resolve_file_not_found(self) -> None:
        """Test resolution failure when file doesn't exist."""
        resolver = SourceResolver()

        with pytest.raises(ValueError, match="Could not resolve identifier"):
            resolver.resolve("/nonexistent/path/agent.yaml")

    def test_resolve_priority_http_over_file(
        self,
        sample_yaml_content: str,
    ) -> None:
        """Test that HTTP URLs are tried before file paths."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = sample_yaml_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Even if there's a file with this name, HTTP should be tried first
            result = resolver.resolve("https://example.com/agent.yaml")

            assert result.source_type == SourceType.HTTP_URL
            mock_get.assert_called_once()


class TestSourceResolution:
    """Test suite for SourceResolution dataclass."""

    def test_agent_resolution_creation(self) -> None:
        """Test creating an SourceResolution instance."""
        resolution = SourceResolution(
            content="test content",
            source="test.yaml",
            source_type=SourceType.FILE_PATH,
            file_path=Path("test.yaml"),
        )

        assert resolution.content == "test content"
        assert resolution.source == "test.yaml"
        assert resolution.source_type == SourceType.FILE_PATH
        assert resolution.file_path == Path("test.yaml")

    def test_agent_resolution_without_file_path(self) -> None:
        """Test creating an SourceResolution without file_path."""
        resolution = SourceResolution(
            content="test content",
            source="https://example.com/agent.yaml",
            source_type=SourceType.HTTP_URL,
        )

        assert resolution.file_path is None
