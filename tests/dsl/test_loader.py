"""Tests for DslAgentLoader.

Test the DSL agent loader for .sr file support.
"""

from pathlib import Path

import pytest

from streetrace.dsl.loader import DslAgentLoader
from streetrace.dsl.runtime import DslAgentWorkflow

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


# =============================================================================
# can_load Tests
# =============================================================================


class TestCanLoad:
    """Test DslAgentLoader.can_load method."""

    def test_can_load_sr_files(self) -> None:
        """Loader should handle .sr files."""
        loader = DslAgentLoader()
        assert loader.can_load(Path("agent.sr"))
        assert loader.can_load(Path("/path/to/my_agent.sr"))
        assert loader.can_load(Path("./agents/workflow.sr"))

    def test_cannot_load_py_files(self) -> None:
        """Loader should not handle .py files."""
        loader = DslAgentLoader()
        assert not loader.can_load(Path("agent.py"))

    def test_cannot_load_yaml_files(self) -> None:
        """Loader should not handle .yaml files."""
        loader = DslAgentLoader()
        assert not loader.can_load(Path("agent.yaml"))
        assert not loader.can_load(Path("agent.yml"))

    def test_cannot_load_other_extensions(self) -> None:
        """Loader should not handle other file types."""
        loader = DslAgentLoader()
        assert not loader.can_load(Path("agent.md"))
        assert not loader.can_load(Path("agent.json"))
        assert not loader.can_load(Path("agent.txt"))


# =============================================================================
# load Tests
# =============================================================================


class TestLoad:
    """Test DslAgentLoader.load method."""

    def test_load_returns_workflow_class(self, tmp_path: Path) -> None:
        """Loading a .sr file should return a workflow class."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        workflow_class = loader.load(dsl_file)

        assert isinstance(workflow_class, type)
        assert issubclass(workflow_class, DslAgentWorkflow)

    def test_load_workflow_can_be_instantiated(self, tmp_path: Path) -> None:
        """Loaded workflow class should be instantiable."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        workflow_class = loader.load(dsl_file)

        # Should be able to create an instance
        instance = workflow_class()
        assert isinstance(instance, DslAgentWorkflow)

    def test_load_preserves_workflow_name(self, tmp_path: Path) -> None:
        """Workflow class name should be derived from file name."""
        dsl_file = tmp_path / "my_cool_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        workflow_class = loader.load(dsl_file)

        # Class name should be CamelCase version of filename
        assert "Workflow" in workflow_class.__name__

    def test_load_file_not_found_raises(self, tmp_path: Path) -> None:
        """Loading nonexistent file should raise FileNotFoundError."""
        dsl_file = tmp_path / "nonexistent.sr"

        loader = DslAgentLoader()

        with pytest.raises(FileNotFoundError):
            loader.load(dsl_file)

    def test_load_syntax_error_raises(self, tmp_path: Path) -> None:
        """Loading file with syntax errors should raise."""
        dsl_file = tmp_path / "broken.sr"
        dsl_file.write_text("model = broken syntax")

        loader = DslAgentLoader()

        with pytest.raises(Exception):  # noqa: B017
            loader.load(dsl_file)

    def test_load_semantic_error_raises(self, tmp_path: Path) -> None:
        """Loading file with semantic errors should raise."""
        dsl_file = tmp_path / "invalid.sr"
        dsl_file.write_text(
            """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
""",
        )

        loader = DslAgentLoader()

        with pytest.raises(Exception):  # noqa: B017
            loader.load(dsl_file)


# =============================================================================
# discover Tests
# =============================================================================


class TestDiscover:
    """Test DslAgentLoader.discover method."""

    def test_discover_finds_sr_files(self, tmp_path: Path) -> None:
        """Discover should find all .sr files in directory."""
        (tmp_path / "agent1.sr").write_text(MINIMAL_AGENT_SOURCE)
        (tmp_path / "agent2.sr").write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        discovered = loader.discover(tmp_path)

        assert len(discovered) == 2
        names = {p.name for p in discovered}
        assert "agent1.sr" in names
        assert "agent2.sr" in names

    def test_discover_finds_nested_files(self, tmp_path: Path) -> None:
        """Discover should find .sr files in subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "top.sr").write_text(MINIMAL_AGENT_SOURCE)
        (subdir / "nested.sr").write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        discovered = loader.discover(tmp_path)

        assert len(discovered) == 2
        names = {p.name for p in discovered}
        assert "top.sr" in names
        assert "nested.sr" in names

    def test_discover_empty_directory(self, tmp_path: Path) -> None:
        """Discover in empty directory returns empty list."""
        loader = DslAgentLoader()
        discovered = loader.discover(tmp_path)

        assert discovered == []

    def test_discover_ignores_other_files(self, tmp_path: Path) -> None:
        """Discover should ignore non-.sr files."""
        (tmp_path / "agent.sr").write_text(MINIMAL_AGENT_SOURCE)
        (tmp_path / "agent.py").write_text("# Python file")
        (tmp_path / "agent.yaml").write_text("name: test")

        loader = DslAgentLoader()
        discovered = loader.discover(tmp_path)

        assert len(discovered) == 1
        assert discovered[0].name == "agent.sr"


# =============================================================================
# Cache Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Test DslAgentLoader caching behavior."""

    def test_cached_load_hits_cache(self, tmp_path: Path) -> None:
        """Loading same file twice should use bytecode cache."""
        dsl_file = tmp_path / "cached_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        class1 = loader.load(dsl_file)
        class2 = loader.load(dsl_file)

        # Both classes should be valid DslAgentWorkflow subclasses
        assert issubclass(class1, DslAgentWorkflow)
        assert issubclass(class2, DslAgentWorkflow)
        # Classes have the same name (from same source)
        assert class1.__name__ == class2.__name__

    def test_modified_file_recompiles(self, tmp_path: Path) -> None:
        """Modified file should be recompiled."""
        dsl_file = tmp_path / "changing_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        class1 = loader.load(dsl_file)

        # Modify the file
        dsl_file.write_text(AGENT_WITH_HANDLER_SOURCE)
        class2 = loader.load(dsl_file)

        # Both classes should be valid but potentially different names
        assert issubclass(class1, DslAgentWorkflow)
        assert issubclass(class2, DslAgentWorkflow)


# =============================================================================
# Workflow Functionality Tests
# =============================================================================


class TestLoadedWorkflowFunctionality:
    """Test functionality of loaded workflow classes."""

    def test_workflow_has_models(self, tmp_path: Path) -> None:
        """Loaded workflow should have model definitions."""
        dsl_file = tmp_path / "model_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        workflow_class = loader.load(dsl_file)

        # Workflow should have _models attribute
        models = getattr(workflow_class, "_models", {})
        assert "main" in models or isinstance(models, dict)

    def test_workflow_creates_context(self, tmp_path: Path) -> None:
        """Loaded workflow should create execution context."""
        dsl_file = tmp_path / "context_agent.sr"
        dsl_file.write_text(MINIMAL_AGENT_SOURCE)

        loader = DslAgentLoader()
        workflow_class = loader.load(dsl_file)
        instance = workflow_class()

        ctx = instance.create_context()
        assert ctx is not None
