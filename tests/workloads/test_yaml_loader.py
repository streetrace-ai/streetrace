"""Tests for YamlDefinitionLoader class."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.agents.yaml_models import YamlAgentSpec
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

if TYPE_CHECKING:
    from streetrace.workloads.yaml_loader import YamlDefinitionLoader


# Valid YAML agent content for testing
VALID_YAML_AGENT = """\
name: test_agent
description: A test agent for unit tests
model: anthropic/claude-sonnet
instruction: You are a helpful assistant.
"""

# YAML agent with all fields
FULL_YAML_AGENT = """\
version: "1.0.0"
kind: agent
name: full_agent
description: An agent with all fields populated
model: openai/gpt-4
instruction: You are a comprehensive assistant.
global_instruction: Global context for all conversations.
prompt: What can I help you with today?
attributes:
  category: testing
  priority: high
"""

# Invalid YAML (syntax error - unbalanced quotes)
INVALID_YAML_SYNTAX = """\
name: "test_agent
description: A test agent
model: test
"""

# YAML without required name field
YAML_MISSING_NAME = """\
description: Agent without a name
model: anthropic/claude-sonnet
"""

# YAML without required description field
YAML_MISSING_DESCRIPTION = """\
name: no_description_agent
model: anthropic/claude-sonnet
"""

# YAML with invalid name (not a valid Python identifier)
YAML_INVALID_NAME = """\
name: 123-invalid-name
description: Agent with invalid name
model: anthropic/claude-sonnet
"""


def make_resolution(
    content: str,
    source: str = "test.yaml",
    file_path: Path | None = None,
) -> SourceResolution:
    """Create a SourceResolution for testing."""
    return SourceResolution(
        content=content,
        source=source,
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format="yaml",
    )


class TestYamlDefinitionLoaderLoad:
    """Test YamlDefinitionLoader.load() method."""

    @pytest.fixture
    def loader(self) -> "YamlDefinitionLoader":
        """Create a YamlDefinitionLoader instance."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        return YamlDefinitionLoader()

    def test_load_parses_valid_yaml_content(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load parses valid YAML content and returns YamlWorkloadDefinition."""
        yaml_file = tmp_path / "valid_agent.yaml"
        resolution = make_resolution(VALID_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        assert isinstance(definition, YamlWorkloadDefinition)
        assert definition.name == "test_agent"
        assert definition.metadata.source_path == yaml_file
        assert definition.metadata.format == "yaml"
        assert isinstance(definition.spec, YamlAgentSpec)

    def test_load_parses_yaml_with_all_fields(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load parses YAML with all fields populated."""
        yaml_file = tmp_path / "full_agent.yaml"
        resolution = make_resolution(FULL_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        assert definition.spec.name == "full_agent"
        assert definition.spec.description == "An agent with all fields populated"
        assert definition.spec.model == "openai/gpt-4"
        assert definition.spec.instruction == "You are a comprehensive assistant."
        expected_global = "Global context for all conversations."
        assert definition.spec.global_instruction == expected_global
        assert definition.spec.prompt == "What can I help you with today?"
        assert definition.spec.attributes == {"category": "testing", "priority": "high"}

    def test_load_raises_for_invalid_yaml_syntax(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises AgentValidationError for invalid YAML syntax."""
        from streetrace.agents.base_agent_loader import AgentValidationError

        invalid_file = tmp_path / "invalid.yaml"
        src = str(invalid_file)
        resolution = make_resolution(INVALID_YAML_SYNTAX, src, invalid_file)

        with pytest.raises(AgentValidationError):
            loader.load(resolution)

    def test_load_raises_for_missing_name_field(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises AgentValidationError for YAML missing required name."""
        from streetrace.agents.base_agent_loader import AgentValidationError

        invalid_file = tmp_path / "no_name.yaml"
        resolution = make_resolution(YAML_MISSING_NAME, str(invalid_file), invalid_file)

        with pytest.raises(AgentValidationError):
            loader.load(resolution)

    def test_load_raises_for_missing_description_field(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises AgentValidationError for YAML missing description."""
        from streetrace.agents.base_agent_loader import AgentValidationError

        invalid_file = tmp_path / "no_description.yaml"
        resolution = make_resolution(
            YAML_MISSING_DESCRIPTION, str(invalid_file), invalid_file,
        )

        with pytest.raises(AgentValidationError):
            loader.load(resolution)

    def test_load_raises_for_invalid_agent_name(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises AgentValidationError for invalid agent name."""
        from streetrace.agents.base_agent_loader import AgentValidationError

        invalid_file = tmp_path / "invalid_name.yaml"
        resolution = make_resolution(YAML_INVALID_NAME, str(invalid_file), invalid_file)

        with pytest.raises(AgentValidationError):
            loader.load(resolution)

    def test_load_extracts_name_from_spec(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load extracts workload name from YAML spec."""
        yaml_file = tmp_path / "any_filename.yaml"
        resolution = make_resolution(VALID_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        # Name comes from the spec, not the filename
        assert definition.name == "test_agent"
        assert definition.metadata.name == "test_agent"

    def test_load_extracts_description_from_spec(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load extracts description from YAML spec."""
        yaml_file = tmp_path / "agent.yaml"
        resolution = make_resolution(VALID_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        assert definition.metadata.description == "A test agent for unit tests"

    def test_load_works_without_file_path(
        self, loader: "YamlDefinitionLoader",
    ) -> None:
        """Test load works when file_path is None (e.g., HTTP source)."""
        resolution = make_resolution(
            VALID_YAML_AGENT,
            "https://example.com/agent.yaml",
            None,
        )

        definition = loader.load(resolution)

        assert isinstance(definition, YamlWorkloadDefinition)
        assert definition.metadata.source_path is None
        assert definition.name == "test_agent"  # From spec, not URL

    def test_load_raises_for_non_mapping_yaml(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises AgentValidationError when YAML is not a mapping."""
        from streetrace.agents.base_agent_loader import AgentValidationError

        list_yaml = "- item1\n- item2\n"
        yaml_file = tmp_path / "list.yaml"
        resolution = make_resolution(list_yaml, str(yaml_file), yaml_file)

        with pytest.raises(AgentValidationError, match="must contain a mapping"):
            loader.load(resolution)


class TestYamlDefinitionLoaderProtocolCompliance:
    """Test that YamlDefinitionLoader satisfies the DefinitionLoader protocol."""

    def test_satisfies_definition_loader_protocol(self) -> None:
        """Test YamlDefinitionLoader satisfies the DefinitionLoader protocol."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = YamlDefinitionLoader()

        assert isinstance(loader, DefinitionLoader)

    def test_has_load_method(self) -> None:
        """Test YamlDefinitionLoader has load method."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = YamlDefinitionLoader()

        assert hasattr(loader, "load")
        assert callable(loader.load)


class TestYamlDefinitionLoaderMetadataExtraction:
    """Test metadata extraction from YAML content."""

    @pytest.fixture
    def loader(self) -> "YamlDefinitionLoader":
        """Create a YamlDefinitionLoader instance."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        return YamlDefinitionLoader()

    def test_metadata_has_correct_format(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition has format='yaml' in metadata."""
        yaml_file = tmp_path / "format_test.yaml"
        resolution = make_resolution(VALID_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        assert definition.metadata.format == "yaml"

    def test_metadata_has_source_path(
        self, loader: "YamlDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition preserves the source path."""
        yaml_file = tmp_path / "path_test.yaml"
        resolution = make_resolution(VALID_YAML_AGENT, str(yaml_file), yaml_file)

        definition = loader.load(resolution)

        assert definition.metadata.source_path == yaml_file


class TestYamlDefinitionLoaderHttpAuth:
    """Test YamlDefinitionLoader HTTP auth configuration."""

    def test_loader_accepts_http_auth(self) -> None:
        """Test loader can be initialized with http_auth."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = YamlDefinitionLoader(http_auth="Bearer token123")

        assert loader._http_auth == "Bearer token123"  # noqa: SLF001

    def test_loader_defaults_to_no_auth(self) -> None:
        """Test loader defaults to None http_auth."""
        from streetrace.workloads.yaml_loader import YamlDefinitionLoader

        loader = YamlDefinitionLoader()

        assert loader._http_auth is None  # noqa: SLF001
