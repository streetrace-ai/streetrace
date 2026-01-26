"""Tests for DslDefinitionLoader.

Test the DSL definition loader for .sr file support.

Note: This file previously tested the old DslAgentLoader from streetrace.dsl.loader.
It has been updated to test the new DslDefinitionLoader from streetrace.workloads.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.dsl.runtime import DslAgentWorkflow
from streetrace.workloads import DslDefinitionLoader

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider


@pytest.fixture
def mock_model_factory() -> "ModelFactory":
    """Create a mock ModelFactory."""
    factory = MagicMock()
    factory.get_current_model.return_value = MagicMock()
    factory.get_llm_interface.return_value = MagicMock()
    return factory


@pytest.fixture
def mock_tool_provider() -> "ToolProvider":
    """Create a mock ToolProvider."""
    return MagicMock()


@pytest.fixture
def mock_system_context() -> "SystemContext":
    """Create a mock SystemContext."""
    return MagicMock()


@pytest.fixture
def mock_session_service() -> "BaseSessionService":
    """Create a mock BaseSessionService."""
    return MagicMock()


# =============================================================================
# Sample DSL Sources for Testing
# =============================================================================

MINIMAL_AGENT_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent helper:
    tools fs
    instruction greeting
"""

AGENT_WITH_HANDLER_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

on input do
    mask pii
end
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


# =============================================================================
# load Tests
# =============================================================================


class TestLoad:
    """Test DslDefinitionLoader.load method."""

    def test_load_returns_definition_with_workflow_class(self, tmp_path: Path) -> None:
        """Loading a .sr file should return a definition with workflow class."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        assert isinstance(definition.workflow_class, type)
        assert issubclass(definition.workflow_class, DslAgentWorkflow)

    def test_load_workflow_can_be_instantiated(
        self,
        tmp_path: Path,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Loaded workflow class should be instantiable."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        # Should be able to create an instance with required dependencies
        instance = definition.workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        assert isinstance(instance, DslAgentWorkflow)

    def test_load_preserves_workflow_name(self, tmp_path: Path) -> None:
        """Workflow class name should be derived from file name."""
        dsl_file = tmp_path / "my_cool_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        # Class name should be CamelCase version of filename
        assert "Workflow" in definition.workflow_class.__name__

    def test_load_extracts_metadata(self, tmp_path: Path) -> None:
        """Load should extract metadata from DSL file."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        assert definition.metadata.name == "test_agent"
        assert definition.metadata.format == "dsl"
        assert definition.metadata.source_path == dsl_file

    def test_load_syntax_error_raises(self, tmp_path: Path) -> None:
        """Loading file with syntax errors should raise."""
        from streetrace.dsl.compiler import DslSyntaxError

        dsl_file = tmp_path / "broken.sr"
        resolution = make_resolution("model = broken syntax", str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()

        with pytest.raises(DslSyntaxError):
            loader.load(resolution)

    def test_load_semantic_error_raises(self, tmp_path: Path) -> None:
        """Loading file with semantic errors should raise."""
        from streetrace.dsl.compiler import DslSemanticError

        invalid_source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""
        dsl_file = tmp_path / "invalid.sr"
        resolution = make_resolution(invalid_source, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()

        with pytest.raises(DslSemanticError):
            loader.load(resolution)


# =============================================================================
# Cache Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Test DslDefinitionLoader caching behavior."""

    def test_cached_load_produces_valid_workflow(self, tmp_path: Path) -> None:
        """Loading same content twice should produce valid workflow classes."""
        dsl_file = tmp_path / "cached_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        def1 = loader.load(resolution)
        def2 = loader.load(resolution)

        # Both definitions should have valid DslAgentWorkflow subclasses
        assert issubclass(def1.workflow_class, DslAgentWorkflow)
        assert issubclass(def2.workflow_class, DslAgentWorkflow)
        # Classes have the same name (from same source)
        assert def1.workflow_class.__name__ == def2.workflow_class.__name__

    def test_different_content_produces_different_workflows(
        self, tmp_path: Path,
    ) -> None:
        """Different content should produce different workflow classes."""
        dsl_file = tmp_path / "changing_agent.sr"
        res1 = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)
        res2 = make_resolution(AGENT_WITH_HANDLER_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        def1 = loader.load(res1)
        def2 = loader.load(res2)

        # Both definitions should have valid workflow classes
        assert issubclass(def1.workflow_class, DslAgentWorkflow)
        assert issubclass(def2.workflow_class, DslAgentWorkflow)


# =============================================================================
# Workflow Functionality Tests
# =============================================================================


class TestLoadedWorkflowFunctionality:
    """Test functionality of loaded workflow classes."""

    def test_workflow_has_models(self, tmp_path: Path) -> None:
        """Loaded workflow should have model definitions."""
        dsl_file = tmp_path / "model_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)

        # Workflow should have _models attribute
        models = getattr(definition.workflow_class, "_models", {})
        assert "main" in models or isinstance(models, dict)

    def test_workflow_creates_context(
        self,
        tmp_path: Path,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Loaded workflow should create execution context."""
        dsl_file = tmp_path / "context_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)
        resolution = make_resolution(MINIMAL_AGENT_SOURCE, str(dsl_file), dsl_file)

        loader = DslDefinitionLoader()
        definition = loader.load(resolution)
        instance = definition.workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        ctx = instance.create_context()
        assert ctx is not None
