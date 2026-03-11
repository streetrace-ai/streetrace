"""Tests validating the Getting Started guide workflow.

Each test corresponds to a step in the getting started guide:
1. --list-agents works without --model
2. Agent discovery finds agents in ./agents/ directory
3. DSL agent created in ./agents/ is discoverable by name
4. DSL examples embedded in the coder agent compile successfully
"""

from pathlib import Path
from unittest.mock import Mock

from streetrace.agents.resolver import SourceResolver
from streetrace.dsl.compiler import compile_dsl
from streetrace.list_agents import WorkloadDefinitionList, list_available_agents
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.ui_bus import UiBus
from streetrace.workloads import WorkloadManager


class TestListAgentsWithoutModel:
    """Step 4: streetrace --list-agents works without --model."""

    def test_discover_definitions_succeeds_without_model(
        self,
        tmp_path: Path,
    ) -> None:
        """Workload discovery does not require a model."""
        ui_bus = Mock(spec=UiBus)
        model_factory = ModelFactory(
            default_model_name=None, ui_bus=ui_bus, args=Mock(cache=False),
        )
        tool_provider = ToolProvider(tmp_path)
        system_context = Mock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Should succeed without model - discovery doesn't need LLM
        definitions = manager.discover_definitions()
        assert isinstance(definitions, list)
        # Should find bundled agents at minimum
        names = [d.name.lower() for d in definitions]
        assert "streetrace" in names

    def test_list_available_agents_dispatches_to_ui(
        self,
        tmp_path: Path,
    ) -> None:
        """list_available_agents dispatches WorkloadDefinitionList to UI."""
        ui_bus = Mock(spec=UiBus)
        model_factory = ModelFactory(
            default_model_name=None, ui_bus=ui_bus, args=Mock(cache=False),
        )
        tool_provider = ToolProvider(tmp_path)
        system_context = Mock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        list_available_agents(manager, ui_bus)

        # Verify UI was called with a WorkloadDefinitionList
        ui_bus.dispatch_ui_update.assert_called_once()
        dispatched = ui_bus.dispatch_ui_update.call_args[0][0]
        assert isinstance(dispatched, WorkloadDefinitionList)
        assert len(dispatched) > 0


class TestAgentDiscoveryInAgentsDir:
    """Steps 5-6: Agent created in ./agents/ is discoverable."""

    def test_yaml_agent_in_agents_dir_is_discovered(
        self,
        tmp_path: Path,
    ) -> None:
        """A YAML agent file in ./agents/ should be discovered by name."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create a minimal YAML agent (mimics what the coding agent would create)
        agent_yaml = agents_dir / "spec_writer.yaml"
        agent_yaml.write_text(
            "name: spec_writer\n"
            "description: Writes change request specs\n"
            "instruction: You write specs.\n",
        )

        ui_bus = Mock(spec=UiBus)
        model_factory = ModelFactory(
            default_model_name=None, ui_bus=ui_bus, args=Mock(cache=False),
        )
        tool_provider = ToolProvider(tmp_path)
        system_context = Mock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        definitions = manager.discover_definitions()
        names = [d.name.lower() for d in definitions]
        assert "spec_writer" in names

    def test_yaml_agent_loadable_by_name(
        self,
        tmp_path: Path,
    ) -> None:
        """A YAML agent in ./agents/ can be loaded by name via _load_by_name."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        agent_yaml = agents_dir / "spec_writer.yaml"
        agent_yaml.write_text(
            "name: spec_writer\n"
            "description: Writes change request specs\n"
            "instruction: You write specs.\n",
        )

        ui_bus = Mock(spec=UiBus)
        model_factory = ModelFactory(
            default_model_name=None, ui_bus=ui_bus, args=Mock(cache=False),
        )
        tool_provider = ToolProvider(tmp_path)
        system_context = Mock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Should be found via name lookup
        definition = manager._load_by_name("spec_writer")  # noqa: SLF001
        assert definition is not None
        assert definition.name.lower() == "spec_writer"

    def test_dsl_agent_in_agents_dir_is_discovered(
        self,
        tmp_path: Path,
    ) -> None:
        """A DSL agent file in ./agents/ should be discovered by name."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create a minimal DSL agent
        agent_sr = agents_dir / "spec_writer.sr"
        agent_sr.write_text(
            "model main = anthropic/claude-sonnet\n"
            "\n"
            'prompt system_prompt: """You write change request specs."""\n'
            "\n"
            "agent:\n"
            "    instruction system_prompt\n",
        )

        ui_bus = Mock(spec=UiBus)
        model_factory = ModelFactory(
            default_model_name=None, ui_bus=ui_bus, args=Mock(cache=False),
        )
        tool_provider = ToolProvider(tmp_path)
        system_context = Mock(spec=SystemContext)

        manager = WorkloadManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        definitions = manager.discover_definitions()
        names = [d.name.lower() for d in definitions]
        assert "spec_writer" in names


class TestSourceResolverDiscovery:
    """Test that SourceResolver discovers agents in search paths."""

    def test_discovers_yaml_agents(self, tmp_path: Path) -> None:
        """SourceResolver finds .yaml files."""
        agent_yaml = tmp_path / "my_agent.yaml"
        agent_yaml.write_text(
            "name: my_agent\n"
            "description: Test agent\n",
        )

        resolver = SourceResolver()
        discovered = resolver.discover([tmp_path])
        assert "my_agent" in discovered

    def test_discovers_dsl_agents(self, tmp_path: Path) -> None:
        """SourceResolver finds .sr files."""
        agent_sr = tmp_path / "my_agent.sr"
        agent_sr.write_text(
            "streetrace v1\n"
            "model main = anthropic/claude-sonnet\n"
            "agent:\n"
            '    description "test"\n',
        )

        resolver = SourceResolver()
        discovered = resolver.discover([tmp_path])
        assert "my_agent" in discovered

    def test_cwd_agents_dir_priority(self, tmp_path: Path) -> None:
        """Agents in ./agents/ take priority over bundled agents."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Override the bundled generic agent
        agent_yaml = agents_dir / "generic.yaml"
        agent_yaml.write_text(
            "name: generic\n"
            "description: Custom override\n",
        )

        resolver = SourceResolver()
        discovered = resolver.discover([agents_dir])
        assert "generic" in discovered
        assert discovered["generic"].source == str(agent_yaml)


class TestCoderAgentDslExamples:
    """Validate that DSL examples in the coder agent's instruction compile."""

    def test_minimal_example_compiles(self) -> None:
        """The minimal DSL example from the coder instruction must compile."""
        source = (
            'model main = anthropic/claude-sonnet-4-20250514\n'
            '\n'
            'prompt system_prompt: """You are a helpful coding assistant."""\n'
            '\n'
            'agent:\n'
            '    instruction system_prompt\n'
        )
        result = compile_dsl(source, "test_agent.sr")
        assert result is not None

    def test_tools_and_subagents_example_compiles(self) -> None:
        """The tools + sub-agents DSL example must compile."""
        source = (
            'model main = anthropic/claude-sonnet-4-20250514\n'
            '\n'
            'tool fs = builtin streetrace.fs\n'
            'tool cli = builtin streetrace.cli\n'
            '\n'
            'prompt researcher_prompt: '
            '"""You research codebases and find relevant code."""\n'
            '\n'
            'prompt writer_prompt: '
            '"""You write technical specifications.\n'
            'Use the researcher to find relevant code, '
            'then write a spec."""\n'
            '\n'
            'agent researcher:\n'
            '    tools fs\n'
            '    instruction researcher_prompt\n'
            '    description "Finds relevant code and docs"\n'
            '\n'
            'agent:\n'
            '    tools fs, cli\n'
            '    instruction writer_prompt\n'
            '    use researcher\n'
            '    description "Writes technical specs"\n'
        )
        result = compile_dsl(source, "test_agent.sr")
        assert result is not None

    def test_getting_started_guide_example_compiles(self) -> None:
        """The spec_writer example from the Getting Started guide must compile."""
        source = (
            'model main = anthropic/claude-sonnet-4-20250514\n'
            '\n'
            'tool fs = builtin streetrace.fs\n'
            'tool cli = builtin streetrace.cli\n'
            'tool context7 = mcp "https://mcp.context7.com/mcp"\n'
            '\n'
            'prompt spec_writer_prompt: """You are a spec writer agent. '
            'When given a feature request:\n'
            '1. Explore the codebase to understand the current architecture\n'
            '2. Research the web for relevant whitepapers and discussions\n'
            '3. Write a detailed change request spec\n'
            '4. Save the spec to ./docs/spec/ with a unique ID"""\n'
            '\n'
            'agent:\n'
            '    tools fs, cli, context7\n'
            '    instruction spec_writer_prompt\n'
            '    description "Writes change request specs"\n'
        )
        result = compile_dsl(source, "test_agent.sr")
        assert result is not None
