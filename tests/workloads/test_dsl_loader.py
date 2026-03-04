"""Tests for DslDefinitionLoader class."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.loader import DefinitionLoader

if TYPE_CHECKING:
    from streetrace.workloads.dsl_loader import DslDefinitionLoader

# Valid DSL source for testing
VALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent:
    tools fs
    instruction greeting
"""

# DSL with description comment
DSL_WITH_DESCRIPTION = """\
# This is a test agent with a custom description
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

agent:
    instruction greeting
"""

# Invalid DSL source (syntax error)
INVALID_DSL_SYNTAX = """\
streetrace v1

model main =

agent:
    instruction greeting
"""

# DSL without workflow class (malformed)
DSL_MISSING_AGENT = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"
"""


def make_resolution(
    content: str,
    source: str = "test.sr",
    file_path: Path | None = None,
) -> SourceResolution:
    """Create a SourceResolution for testing."""
    return SourceResolution(
        content=content,
        source=source,
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format="dsl",
    )


class TestDslDefinitionLoaderLoad:
    """Test DslDefinitionLoader.load() method."""

    @pytest.fixture
    def loader(self) -> "DslDefinitionLoader":
        """Create a DslDefinitionLoader instance."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        return DslDefinitionLoader()

    def test_load_compiles_valid_dsl_content(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load compiles valid DSL content and returns DslWorkloadDefinition."""
        dsl_file = tmp_path / "valid_agent.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert isinstance(definition, DslWorkloadDefinition)
        assert definition.name == "valid_agent"
        assert definition.metadata.source_path == dsl_file
        assert definition.metadata.format == "dsl"
        assert issubclass(definition.workflow_class, DslAgentWorkflow)

    def test_load_raises_for_invalid_syntax(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises DslSyntaxError for invalid syntax."""
        from streetrace.dsl.compiler import DslSyntaxError

        invalid_file = tmp_path / "invalid.sr"
        src = str(invalid_file)
        resolution = make_resolution(INVALID_DSL_SYNTAX, src, invalid_file)

        with pytest.raises(DslSyntaxError):
            loader.load(resolution)

    def test_load_dsl_without_agent_still_produces_workflow(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load succeeds for DSL without agent (produces workflow anyway).

        The DSL compiler always generates a workflow class even if no agent
        is defined. This tests that such files load successfully.
        """
        no_agent_file = tmp_path / "no_agent.sr"
        src = str(no_agent_file)
        resolution = make_resolution(DSL_MISSING_AGENT, src, no_agent_file)

        definition = loader.load(resolution)
        assert isinstance(definition, DslWorkloadDefinition)
        assert issubclass(definition.workflow_class, DslAgentWorkflow)

    def test_load_extracts_name_from_filename(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load extracts workload name from filename."""
        dsl_file = tmp_path / "my_custom_agent.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert definition.name == "my_custom_agent"
        assert definition.metadata.name == "my_custom_agent"

    def test_load_extracts_description_from_comment(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load extracts description from first comment line."""
        dsl_file = tmp_path / "described_agent.sr"
        resolution = make_resolution(DSL_WITH_DESCRIPTION, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert "test agent with a custom description" in definition.metadata.description

    def test_load_provides_default_description(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load provides default description when no comment exists."""
        dsl_file = tmp_path / "no_comment_agent.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert "no_comment_agent.sr" in definition.metadata.description

    def test_load_returns_source_map(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load returns source mappings."""
        dsl_file = tmp_path / "mapped_agent.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert isinstance(definition.source_map, list)

    def test_load_compiles_immediately_not_deferred(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load compiles DSL immediately, not deferred."""
        dsl_file = tmp_path / "immediate_compile.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert definition.workflow_class is not None
        assert issubclass(definition.workflow_class, DslAgentWorkflow)

    def test_load_works_without_file_path(
        self, loader: "DslDefinitionLoader",
    ) -> None:
        """Test load works when file_path is None (e.g., HTTP source)."""
        resolution = make_resolution(
            VALID_DSL_SOURCE,
            "https://example.com/agent.sr",
            None,
        )

        definition = loader.load(resolution)

        assert isinstance(definition, DslWorkloadDefinition)
        assert definition.metadata.source_path is None
        assert definition.name == "agent"  # Extracted from URL


class TestDslDefinitionLoaderProtocolCompliance:
    """Test that DslDefinitionLoader satisfies the DefinitionLoader protocol."""

    def test_satisfies_definition_loader_protocol(self) -> None:
        """Test DslDefinitionLoader satisfies the DefinitionLoader protocol."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        loader = DslDefinitionLoader()

        assert isinstance(loader, DefinitionLoader)

    def test_has_load_method(self) -> None:
        """Test DslDefinitionLoader has load method."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        loader = DslDefinitionLoader()

        assert hasattr(loader, "load")
        assert callable(loader.load)


class TestDslDefinitionLoaderInitOverrideGuard:
    """Test that generated workflow classes cannot override __init__."""

    @pytest.fixture
    def loader(self) -> "DslDefinitionLoader":
        """Create a DslDefinitionLoader instance."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        return DslDefinitionLoader()

    def test_generated_class_does_not_override_init(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test normal DSL compilation produces class without __init__ override."""
        dsl_file = tmp_path / "normal.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert "__init__" not in definition.workflow_class.__dict__

    def test_rejects_class_with_init_override(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loader rejects workflow class that overrides __init__.

        This tests the fool-proof check that prevents compiler bugs from
        breaking the constructor-based dependency injection contract.
        """

        class BadWorkflow(DslAgentWorkflow):
            """Simulates a hypothetical compiler bug that adds __init__."""

            def __init__(self) -> None:
                super().__init__(
                    model_factory=None,  # type: ignore[arg-type]
                    tool_provider=None,  # type: ignore[arg-type]
                    system_context=None,  # type: ignore[arg-type]
                    session_service=None,  # type: ignore[arg-type]
                )

        namespace = {
            "DslAgentWorkflow": DslAgentWorkflow,
            "BadWorkflow": BadWorkflow,
        }

        with pytest.raises(ValueError, match="must not override __init__"):
            loader._find_workflow_class(namespace, tmp_path / "bad.sr")  # noqa: SLF001


class TestDslDefinitionLoaderMetadataExtraction:
    """Test metadata extraction from compiled DSL class."""

    @pytest.fixture
    def loader(self) -> "DslDefinitionLoader":
        """Create a DslDefinitionLoader instance."""
        from streetrace.workloads.dsl_loader import DslDefinitionLoader

        return DslDefinitionLoader()

    def test_metadata_has_correct_format(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition has format='dsl' in metadata."""
        dsl_file = tmp_path / "format_test.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert definition.metadata.format == "dsl"

    def test_metadata_has_source_path(
        self, loader: "DslDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition preserves the source path."""
        dsl_file = tmp_path / "path_test.sr"
        resolution = make_resolution(VALID_DSL_SOURCE, str(dsl_file), dsl_file)

        definition = loader.load(resolution)

        assert definition.metadata.source_path == dsl_file
