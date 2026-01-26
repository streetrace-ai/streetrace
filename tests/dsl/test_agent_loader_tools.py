"""Tests for DSL agent loader tool loading functionality.

Test that tools defined in DSL files are properly loaded and passed
to ADK agents via DslDefinitionLoader and DslAgentFactory.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.workloads.dsl_loader import DslDefinitionLoader


def make_dsl_resolution_from_path(file_path: Path) -> SourceResolution:
    """Create a SourceResolution by reading content from file."""
    content = file_path.read_text()
    return SourceResolution(
        content=content,
        source=str(file_path),
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format="dsl",
    )

# DSL sources for testing tool loading
DSL_WITH_BUILTIN_TOOL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

tool fs = builtin streetrace.fs

agent:
    tools fs
    instruction greeting
"""

DSL_WITH_MCP_TOOL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

tool github = mcp "https://api.github.com/mcp"

agent:
    tools github
    instruction greeting
"""

DSL_WITH_MULTIPLE_TOOLS = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

tool fs = builtin streetrace.fs
tool github = mcp "https://api.github.com/mcp"
tool context7 = mcp "https://mcp.context7.com/mcp"

agent:
    tools fs
    instruction greeting
"""
# NOTE: Multiple comma-separated tools (tools fs, github, context7) has a bug
# in the AST transformer that includes commas in the tool list.
# See tech_debt.md for tracking.

DSL_WITH_NO_TOOLS = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

agent:
    instruction greeting
"""


class TestToolLoadingFromDsl:
    """Test tool loading from DSL files."""

    @pytest.fixture
    def mock_model_factory(self) -> MagicMock:
        """Create a mock model factory."""
        factory = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_adk_llm.return_value = MagicMock()
        factory.get_llm_interface.return_value = mock_llm
        factory.get_current_model.return_value = MagicMock()
        return factory

    @pytest.fixture
    def mock_tool_provider(self) -> MagicMock:
        """Create a mock tool provider."""
        from streetrace.tools.tool_provider import ToolProvider

        provider = MagicMock(spec=ToolProvider)
        provider.get_tools.return_value = [MagicMock()]
        provider.work_dir = Path.cwd()
        return provider

    @pytest.fixture
    def mock_system_context(self) -> MagicMock:
        """Create a mock system context."""
        from streetrace.system_context import SystemContext

        return MagicMock(spec=SystemContext)

    def test_builtin_tool_loading_from_dsl(self, tmp_path: Path) -> None:
        """Builtin tools defined in DSL are loaded into agent."""
        # Create DSL file with builtin tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_BUILTIN_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the workflow class has the tool defined
        workflow_class = agent_factory.workflow_class
        assert hasattr(workflow_class, "_tools")
        assert "fs" in workflow_class._tools  # noqa: SLF001
        assert workflow_class._tools["fs"]["type"] == "builtin"  # noqa: SLF001

    def test_mcp_tool_loading_from_dsl(self, tmp_path: Path) -> None:
        """MCP tools defined in DSL are loaded into agent."""
        # Create DSL file with MCP tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MCP_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the workflow class has the tool defined
        workflow_class = agent_factory.workflow_class
        assert hasattr(workflow_class, "_tools")
        assert "github" in workflow_class._tools  # noqa: SLF001
        assert workflow_class._tools["github"]["type"] == "mcp"  # noqa: SLF001
        assert workflow_class._tools["github"]["url"] == "https://api.github.com/mcp"  # noqa: SLF001

    def test_multiple_tools_defined_in_dsl(self, tmp_path: Path) -> None:
        """Multiple tools defined in DSL are all stored in _tools dict."""
        # Create DSL file with multiple tools defined (even if agent only uses one)
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_TOOLS)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the workflow class has all tools defined
        workflow_class = agent_factory.workflow_class
        assert hasattr(workflow_class, "_tools")
        tools = workflow_class._tools  # noqa: SLF001

        # All defined tools should be in _tools
        assert "fs" in tools
        assert "github" in tools
        assert "context7" in tools
        assert len(tools) == 3

    def test_agent_has_tool_refs_in_agents_dict(self, tmp_path: Path) -> None:
        """Agent definitions include tool references."""
        # Create DSL file with a tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_BUILTIN_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the agent definition includes tools
        workflow_class = agent_factory.workflow_class
        agents = workflow_class._agents  # noqa: SLF001
        default_agent = agents.get("default")

        assert default_agent is not None
        assert "tools" in default_agent
        assert "fs" in default_agent["tools"]

    @pytest.mark.asyncio
    async def test_create_agent_passes_tools_to_llm_agent(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Tools are passed to the LlmAgent during create_agent."""
        # Create DSL file with builtin tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_BUILTIN_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Mock LlmAgent to capture constructor args
        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with tools
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args
            # Check that tools were passed (either as positional or keyword arg)
            assert "tools" in call_kwargs.kwargs or len(call_kwargs.args) > 2

    @pytest.mark.asyncio
    async def test_tool_provider_resolves_builtin_tools(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """ToolProvider is used to resolve builtin tool definitions."""
        from streetrace.tools.tool_provider import ToolProvider

        # Create DSL file with builtin tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_BUILTIN_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Create a real tool provider with mocked internals
        tool_provider = MagicMock(spec=ToolProvider)
        tool_provider.work_dir = tmp_path
        tool_provider.get_tools.return_value = [MagicMock(name="fs_tool")]

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=tool_provider,
                system_context=mock_system_context,
            )

            # Verify tool_provider.get_tools was called
            tool_provider.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_provider_resolves_mcp_tools(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """ToolProvider is used to resolve MCP tool definitions."""
        from streetrace.tools.tool_provider import ToolProvider

        # Create DSL file with MCP tool
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MCP_TOOL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Create a mock tool provider
        tool_provider = MagicMock(spec=ToolProvider)
        tool_provider.work_dir = tmp_path
        tool_provider.get_tools.return_value = [MagicMock(name="github_mcp")]

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=tool_provider,
                system_context=mock_system_context,
            )

            # Verify tool_provider.get_tools was called
            tool_provider.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_with_no_tools_passes_empty_list(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Agent with no tools specified passes empty tools list."""
        # Create DSL file with no tools
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_NO_TOOLS)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs

            # Tools should be empty list or not have dangerous tools
            if "tools" in call_kwargs:
                assert call_kwargs["tools"] == [] or call_kwargs["tools"] is None
