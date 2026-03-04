"""Tests for agent resolver."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from streetrace.agents.resolver import SourceResolution, SourceResolver, SourceType


@dataclass
class AgentInfoStub:
    """Simple stub for agent info in tests."""

    name: str
    description: str
    file_path: Path | None = None


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
def discovered_agents(temp_agent_file: Path) -> list[AgentInfoStub]:
    """Create a list of discovered agents."""
    return [
        AgentInfoStub(
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
        discovered_agents: list[AgentInfoStub],
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
        discovered_agents: list[AgentInfoStub],
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

    def test_agent_resolution_with_format(self) -> None:
        """Test creating an SourceResolution with format field."""
        resolution = SourceResolution(
            content="test content",
            source="test.sr",
            source_type=SourceType.FILE_PATH,
            file_path=Path("test.sr"),
            format="dsl",
        )

        assert resolution.format == "dsl"


class TestFormatDetection:
    """Tests for format detection from file extension and MIME type."""

    def test_detect_format_from_sr_extension(self, tmp_path: Path) -> None:
        """Test that .sr files are detected as DSL format."""
        sr_file = tmp_path / "test.sr"
        sr_file.write_text("streetrace v1")
        resolver = SourceResolver()

        result = resolver.resolve(str(sr_file))

        assert result.format == "dsl"

    def test_detect_format_from_yaml_extension(self, tmp_path: Path) -> None:
        """Test that .yaml files are detected as YAML format."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: test")
        resolver = SourceResolver()

        result = resolver.resolve(str(yaml_file))

        assert result.format == "yaml"

    def test_detect_format_from_yml_extension(self, tmp_path: Path) -> None:
        """Test that .yml files are detected as YAML format."""
        yml_file = tmp_path / "test.yml"
        yml_file.write_text("name: test")
        resolver = SourceResolver()

        result = resolver.resolve(str(yml_file))

        assert result.format == "yaml"

    def test_detect_format_from_python_directory(self, tmp_path: Path) -> None:
        """Test that directories with agent.py are detected as Python format."""
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("# agent code")
        resolver = SourceResolver()

        result = resolver.resolve(str(agent_dir))

        assert result.format == "python"

    def test_detect_format_from_http_yaml_mime_type(self) -> None:
        """Test format detection from HTTP YAML MIME type."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "name: test"
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"Content-Type": "application/yaml; charset=utf-8"}
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent")

            assert result.format == "yaml"

    def test_detect_format_from_http_yaml_url_extension(self) -> None:
        """Test format detection from HTTP URL .yaml extension."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "name: test"
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent.yaml")

            assert result.format == "yaml"

    def test_detect_format_http_default_to_dsl(self) -> None:
        """Test HTTP defaults to DSL format when no YAML indicators."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "some content"
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent")

            assert result.format == "dsl"


class TestHttpSecurityPolicy:
    """Tests for HTTP security policy - only Python is rejected."""

    def test_http_allows_sr_extension(self) -> None:
        """Test that HTTP loading allows .sr files (DSL)."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "streetrace v1"
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent.sr")

            assert result.source_type == SourceType.HTTP_URL
            assert result.format == "dsl"

    def test_http_rejects_py_extension(self) -> None:
        """Test that HTTP loading rejects .py files."""
        resolver = SourceResolver()

        with pytest.raises(ValueError, match="not supported for Python"):
            resolver.resolve("https://example.com/agent.py")

    def test_http_rejects_agent_py_path(self) -> None:
        """Test that HTTP loading rejects URLs containing /agent.py."""
        resolver = SourceResolver()

        with pytest.raises(ValueError, match="not supported for Python"):
            resolver.resolve("https://example.com/myagent/agent.py")

    def test_http_allows_yaml(self) -> None:
        """Test that HTTP loading allows .yaml files."""
        resolver = SourceResolver()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "name: test"
            mock_response.raise_for_status = Mock()
            mock_response.headers = {"Content-Type": "application/yaml"}
            mock_get.return_value = mock_response

            result = resolver.resolve("https://example.com/agent.yaml")

            assert result.source_type == SourceType.HTTP_URL


class TestExclusionLogic:
    """Tests for path exclusion logic."""

    def test_excludes_venv_directory(self) -> None:
        """Test that paths in .venv are excluded."""
        resolver = SourceResolver()
        path = Path("/project/.venv/lib/agent.yaml")

        assert resolver._is_excluded(path) is True  # noqa: SLF001

    def test_excludes_git_directory(self) -> None:
        """Test that paths in .git are excluded."""
        resolver = SourceResolver()
        path = Path("/project/.git/hooks/agent.yaml")

        assert resolver._is_excluded(path) is True  # noqa: SLF001

    def test_excludes_node_modules(self) -> None:
        """Test that paths in node_modules are excluded."""
        resolver = SourceResolver()
        path = Path("/project/node_modules/package/agent.yaml")

        assert resolver._is_excluded(path) is True  # noqa: SLF001

    def test_excludes_pycache(self) -> None:
        """Test that paths in __pycache__ are excluded."""
        resolver = SourceResolver()
        path = Path("/project/__pycache__/agent.yaml")

        assert resolver._is_excluded(path) is True  # noqa: SLF001

    def test_excludes_hidden_directories(self) -> None:
        """Test that paths in hidden directories are excluded."""
        resolver = SourceResolver()
        path = Path("/project/.hidden/agent.yaml")

        assert resolver._is_excluded(path) is True  # noqa: SLF001

    def test_does_not_exclude_normal_path(self) -> None:
        """Test that normal paths are not excluded."""
        resolver = SourceResolver()
        path = Path("/project/agents/my_agent.yaml")

        assert resolver._is_excluded(path) is False  # noqa: SLF001


class TestDiscovery:
    """Tests for agent discovery functionality."""

    def test_discover_dsl_agents(self, tmp_path: Path) -> None:
        """Test discovering .sr files."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "test1.sr").write_text("streetrace v1")
        (agents_dir / "test2.sr").write_text("streetrace v1")

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])

        assert "test1" in discovered
        assert "test2" in discovered
        assert discovered["test1"].format == "dsl"
        assert discovered["test2"].format == "dsl"

    def test_discover_yaml_agents(self, tmp_path: Path) -> None:
        """Test discovering .yaml and .yml files."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "yaml_agent.yaml").write_text("name: test")
        (agents_dir / "yml_agent.yml").write_text("name: test")

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])

        assert "yaml_agent" in discovered
        assert "yml_agent" in discovered
        assert discovered["yaml_agent"].format == "yaml"
        assert discovered["yml_agent"].format == "yaml"

    def test_discover_python_agents(self, tmp_path: Path) -> None:
        """Test discovering Python agent directories."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        python_agent = agents_dir / "my_python_agent"
        python_agent.mkdir()
        (python_agent / "agent.py").write_text("# python agent")

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])

        assert "my_python_agent" in discovered
        assert discovered["my_python_agent"].format == "python"

    def test_discover_excludes_venv(self, tmp_path: Path) -> None:
        """Test that discovery excludes .venv directories."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        venv_dir = agents_dir / ".venv"
        venv_dir.mkdir()
        (venv_dir / "hidden_agent.sr").write_text("streetrace v1")
        (agents_dir / "visible_agent.sr").write_text("streetrace v1")

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])

        assert "visible_agent" in discovered
        assert "hidden_agent" not in discovered

    def test_discover_first_match_wins(self, tmp_path: Path) -> None:
        """Test that first discovered agent with same name wins."""
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "agent.sr").write_text("content1")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "agent.yaml").write_text("name: agent")

        resolver = SourceResolver()
        # dir1 comes first, so its version should win
        discovered = resolver.discover([dir1, dir2])

        assert "agent" in discovered
        assert discovered["agent"].format == "dsl"  # From dir1, not yaml from dir2

    def test_discover_multiple_locations(self, tmp_path: Path) -> None:
        """Test discovery across multiple locations."""
        loc1 = tmp_path / "loc1"
        loc1.mkdir()
        (loc1 / "agent1.sr").write_text("streetrace v1")

        loc2 = tmp_path / "loc2"
        loc2.mkdir()
        (loc2 / "agent2.yaml").write_text("name: test")

        resolver = SourceResolver()
        discovered = resolver.discover([loc1, loc2])

        assert "agent1" in discovered
        assert "agent2" in discovered

    def test_discover_handles_missing_directory(self, tmp_path: Path) -> None:
        """Test that discovery handles non-existent directories gracefully."""
        nonexistent = tmp_path / "nonexistent"

        resolver = SourceResolver()
        discovered = resolver.discover([nonexistent])

        assert discovered == {}

    def test_discover_recursive(self, tmp_path: Path) -> None:
        """Test that discovery is recursive."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        nested = agents_dir / "nested" / "deep"
        nested.mkdir(parents=True)
        (nested / "deep_agent.sr").write_text("streetrace v1")

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])

        assert "deep_agent" in discovered
