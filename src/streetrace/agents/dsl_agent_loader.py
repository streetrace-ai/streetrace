"""DSL agent loader for .sr files.

Provide loading and discovery of Streetrace DSL agent files for integration
with the AgentManager through the AgentLoader interface.
"""

import inspect
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.models.base_llm import BaseLlm

    from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import AdkTool, ToolProvider
    from streetrace.tools.tool_refs import StreetraceToolRef

from streetrace.agents.base_agent_loader import AgentInfo, AgentLoader
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)


class DslAgentInfo(AgentInfo):
    """Agent information container for DSL agents."""

    def __init__(
        self,
        name: str,
        description: str,
        file_path: Path,
        workflow_class: type[DslAgentWorkflow] | None = None,
    ) -> None:
        """Initialize DSL agent info.

        Args:
            name: Agent name.
            description: Agent description.
            file_path: Path to the .sr file.
            workflow_class: Compiled workflow class (optional).

        """
        super().__init__(name=name, description=description, file_path=file_path)
        self.workflow_class = workflow_class

    @property
    def kind(self) -> str:  # type: ignore[override]
        """Get the definition type of the agent."""
        return "dsl"


class DslAgentLoader(AgentLoader):
    """Agent loader for .sr DSL files.

    Discover and load Streetrace DSL files, compiling them to executable
    workflow classes that can be used as agents.
    """

    def __init__(self) -> None:
        """Initialize the DSL agent loader."""
        logger.debug("Created DslAgentLoader")

    def discover_in_paths(self, paths: list[Path]) -> list[AgentInfo]:
        """Discover .sr agents in specific paths.

        Args:
            paths: Specific paths to search in.

        Returns:
            List of discovered DSL agents.

        """
        discovered: list[AgentInfo] = []

        for search_path in paths:
            if not search_path.exists():
                continue

            # Find all .sr files
            if search_path.is_file() and search_path.suffix == ".sr":
                sr_files = [search_path]
            elif search_path.is_dir():
                sr_files = list(search_path.glob("*.sr"))
            else:
                continue

            for sr_file in sr_files:
                try:
                    agent_info = self._extract_agent_info(sr_file)
                    discovered.append(agent_info)
                    logger.debug(
                        "Discovered DSL agent '%s' at %s",
                        agent_info.name,
                        sr_file,
                    )
                except (ValueError, OSError) as e:
                    logger.debug(
                        "Failed to extract agent info from %s: %s",
                        sr_file,
                        e,
                    )

        return discovered

    def _extract_agent_info(self, file_path: Path) -> DslAgentInfo:
        """Extract agent information from a .sr file.

        Args:
            file_path: Path to the .sr file.

        Returns:
            DslAgentInfo with basic metadata.

        """
        # Use filename (without extension) as agent name
        name = file_path.stem

        # Try to extract description from file header comments
        description = f"DSL agent from {file_path.name}"
        try:
            source = file_path.read_text()
            # Look for description in first comment block
            for raw_line in source.split("\n")[:10]:
                stripped = raw_line.strip()
                if stripped.startswith("#"):
                    # Use first comment line as description
                    description = stripped.lstrip("# ").strip()
                    break
        except OSError:
            pass

        return DslAgentInfo(
            name=name,
            description=description,
            file_path=file_path,
        )

    def load_from_path(self, path: Path) -> StreetRaceAgent:
        """Load agent from explicit file path.

        Args:
            path: Path to .sr file.

        Returns:
            Loaded DSL agent.

        Raises:
            ValueError: If cannot load from this path.

        """
        if not path.exists():
            msg = f"DSL file not found: {path}"
            raise ValueError(msg)

        if path.is_dir():
            # Look for .sr files in directory
            sr_files = list(path.glob("*.sr"))
            if not sr_files:
                msg = f"No .sr files found in directory: {path}"
                raise ValueError(msg)
            path = sr_files[0]

        if path.suffix != ".sr":
            msg = f"Not a DSL file (.sr): {path}"
            raise ValueError(msg)

        return self._load_dsl_file(path)

    def load_from_url(self, url: str) -> StreetRaceAgent:
        """Load agent from HTTP URL.

        DSL files from URLs are not currently supported.

        Args:
            url: HTTP(S) URL.

        Raises:
            ValueError: Always, as URL loading is not supported.

        """
        msg = f"Loading DSL agents from URLs is not supported: {url}"
        raise ValueError(msg)

    def load_agent(self, agent_info: AgentInfo) -> StreetRaceAgent:
        """Load agent from AgentInfo (from discovery).

        Args:
            agent_info: Previously discovered agent info.

        Returns:
            Loaded DSL agent.

        Raises:
            ValueError: If cannot load this agent.

        """
        if not agent_info.file_path:
            msg = f"AgentInfo for '{agent_info.name}' has no file path"
            raise ValueError(msg)

        return self._load_dsl_file(agent_info.file_path)

    def _load_dsl_file(self, path: Path) -> StreetRaceAgent:
        """Load and compile a DSL file.

        Args:
            path: Path to the .sr file.

        Returns:
            DslStreetRaceAgent wrapping the compiled workflow.

        Raises:
            ValueError: If compilation fails.

        """
        from streetrace.dsl import DslSemanticError, DslSyntaxError, compile_dsl

        logger.debug("Loading DSL agent from %s", path)

        try:
            source = path.read_text()
        except OSError as e:
            msg = f"Failed to read DSL file {path}: {e}"
            raise ValueError(msg) from e

        try:
            bytecode, source_map = compile_dsl(source, str(path))
        except DslSyntaxError as e:
            msg = f"Syntax error in {path}: {e}"
            raise ValueError(msg) from e
        except DslSemanticError as e:
            msg = f"Semantic error in {path}: {e}"
            raise ValueError(msg) from e

        # Execute bytecode to get workflow class
        namespace: dict[str, object] = {}
        # SECURITY NOTE: exec is used intentionally here to load validated DSL bytecode.
        # The bytecode is generated from a DSL file that has passed semantic analysis.
        # This is similar to how Python's importlib loads compiled .pyc files.
        compiled_exec(bytecode, namespace)

        # Find the generated workflow class
        workflow_class: type[DslAgentWorkflow] | None = None
        for obj_name, obj in namespace.items():
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, DslAgentWorkflow):
                continue
            if obj_name == "DslAgentWorkflow":
                continue
            workflow_class = obj
            break

        if workflow_class is None:
            msg = f"No workflow class found in compiled DSL: {path}"
            raise ValueError(msg)

        logger.debug("Loaded workflow class %s from %s", workflow_class.__name__, path)

        # Create and return the StreetRaceAgent wrapper
        return DslStreetRaceAgent(
            workflow_class=workflow_class,
            source_file=path,
            source_map=source_map,
        )


def compiled_exec(bytecode: CodeType, namespace: dict[str, object]) -> None:
    """Execute compiled bytecode in a namespace.

    This function wraps exec for executing validated DSL bytecode.
    The bytecode has been generated from a DSL source that passed
    semantic validation.

    Args:
        bytecode: Compiled Python bytecode.
        namespace: Namespace to execute in.

    """
    # SECURITY: exec is intentional here for validated DSL bytecode loading.
    exec(bytecode, namespace)  # noqa: S102  # nosec B102


class DslStreetRaceAgent(StreetRaceAgent):
    """StreetRaceAgent wrapper for compiled DSL workflows.

    Wrap a compiled DSL workflow class to implement the StreetRaceAgent
    interface required by the AgentManager.
    """

    def __init__(
        self,
        workflow_class: type[DslAgentWorkflow],
        source_file: Path,
        source_map: list[SourceMapping],
    ) -> None:
        """Initialize the DSL agent wrapper.

        Args:
            workflow_class: Compiled workflow class.
            source_file: Path to the source .sr file.
            source_map: Source mappings for error translation.

        """
        self._workflow_class = workflow_class
        self._source_file = source_file
        self._source_map = source_map
        self._workflow_instance: DslAgentWorkflow | None = None

    def get_agent_card(self) -> "StreetRaceAgentCard":
        """Provide an A2A AgentCard."""
        from a2a.types import AgentCapabilities, AgentSkill

        from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

        name = self._source_file.stem
        skill = AgentSkill(
            id=f"dsl_{name}",
            name=name,
            description=f"DSL agent from {self._source_file.name}",
            tags=["dsl"],
            examples=[f"Use the {name} DSL agent"],
        )
        return StreetRaceAgentCard(
            name=name,
            description=f"DSL agent from {self._source_file.name}",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    async def create_agent(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> "BaseAgent":
        """Create the ADK agent from the DSL workflow.

        Create the root LlmAgent with support for agentic patterns:
        - Coordinator/dispatcher pattern via sub_agents (delegate keyword)
        - Hierarchical pattern via agent_tools (use keyword)

        Args:
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            The root ADK agent.

        """
        from google.adk.agents import LlmAgent

        # Create workflow instance
        self._workflow_instance = self._workflow_class()

        # Get the agent definition from _agents dict
        agent_def = self._get_default_agent_def()

        # Get instruction from the agent's instruction field (not keyword matching)
        instruction = self._resolve_instruction(agent_def)

        # Resolve model following the design spec:
        # 1. Model from prompt's `using model` clause
        # 2. Fall back to model named "main"
        # 3. CLI override (handled by model_factory)
        model = self._resolve_model(model_factory, agent_def)

        # Resolve tools from the agent's tools list
        tools = self._resolve_tools(tool_provider, agent_def)

        # Resolve sub_agents for delegate pattern
        sub_agents = await self._resolve_sub_agents(
            agent_def, model_factory, tool_provider, system_context,
        )

        # Resolve agent_tools for use pattern (adds to tools list)
        agent_tools = await self._resolve_agent_tools(
            agent_def, model_factory, tool_provider, system_context,
        )
        tools.extend(agent_tools)

        # Build LlmAgent with all components
        agent_kwargs: dict[str, Any] = {
            "name": self._source_file.stem,
            "model": model,
            "instruction": instruction,
            "tools": tools,
        }
        if sub_agents:
            agent_kwargs["sub_agents"] = sub_agents

        return LlmAgent(**agent_kwargs)

    def _get_default_agent_def(self) -> dict[str, object]:
        """Get the default agent definition.

        Returns:
            Agent definition dict with tools, instruction, etc.

        """
        if not hasattr(self._workflow_class, "_agents"):
            return {}

        agents = self._workflow_class._agents  # noqa: SLF001
        # Use 'default' agent or first available agent
        if "default" in agents:
            return agents["default"]
        if agents:
            return next(iter(agents.values()))
        return {}

    def _resolve_instruction(self, agent_def: dict[str, object]) -> str:
        """Resolve instruction from agent definition and prompts.

        Read the instruction name from the agent definition, then
        look it up in the prompts dict.

        Args:
            agent_def: Agent definition dict.

        Returns:
            The resolved instruction string.

        """
        default_instruction = ""

        # Get instruction name from agent definition
        instruction_name = agent_def.get("instruction")
        if not instruction_name or not isinstance(instruction_name, str):
            logger.warning("No instruction specified in agent definition")
            return default_instruction

        # Look up in prompts dict
        if not hasattr(self._workflow_class, "_prompts"):
            logger.warning("No prompts defined in workflow")
            return default_instruction

        prompts = self._workflow_class._prompts  # noqa: SLF001
        if instruction_name not in prompts:
            logger.warning("Instruction '%s' not found in prompts", instruction_name)
            return default_instruction

        prompt_value = prompts[instruction_name]

        # Evaluate prompt lambda with empty context
        if callable(prompt_value):
            from streetrace.dsl.runtime.context import WorkflowContext

            ctx = WorkflowContext()
            try:
                return str(prompt_value(ctx))
            except (TypeError, KeyError) as e:
                logger.warning(
                    "Failed to evaluate prompt '%s': %s", instruction_name, e,
                )
                return default_instruction

        return str(prompt_value)

    def _resolve_model(
        self,
        model_factory: "ModelFactory",
        agent_def: dict[str, object],
    ) -> "str | BaseLlm":
        """Resolve the model following the design spec.

        Model resolution priority:
        1. Model from prompt's `using model` clause
        2. Fall back to model named "main"
        3. CLI override (handled by model_factory.get_current_model)

        Args:
            model_factory: Factory for creating LLM models.
            agent_def: Agent definition dict.

        Returns:
            The resolved ADK model.

        """
        models = getattr(self._workflow_class, "_models", {})
        prompt_models = getattr(self._workflow_class, "_prompt_models", {})

        # Get instruction name to look up prompt's model
        instruction_name = agent_def.get("instruction")
        model_name = None

        # 1. Check if the prompt has a specific model
        if instruction_name and instruction_name in prompt_models:
            prompt_model_ref = prompt_models[instruction_name]
            # The prompt model ref is a model name, look it up in _models
            if prompt_model_ref in models:
                model_name = models[prompt_model_ref]
            else:
                # Assume it's a direct model spec
                model_name = prompt_model_ref

        # 2. Fall back to "main" model
        if not model_name and "main" in models:
            model_name = models["main"]

        # 3. Use CLI override or default
        if model_name:
            return model_factory.get_llm_interface(model_name).get_adk_llm()
        return model_factory.get_current_model()

    def _resolve_tools(
        self,
        tool_provider: "ToolProvider",
        agent_def: dict[str, object],
    ) -> list["AdkTool"]:
        """Resolve tools from the agent's tools list.

        Map DSL tool definitions to ADK tool objects using the tool provider.

        Args:
            tool_provider: Provider for tools.
            agent_def: Agent definition dict.

        Returns:
            List of resolved ADK tools.

        """
        from streetrace.tools.mcp_transport import HttpTransport, SseTransport
        from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef

        # Get tool names from agent definition
        tool_names_raw = agent_def.get("tools", [])
        if not tool_names_raw or not isinstance(tool_names_raw, list):
            return []
        tool_names: list[str] = [t for t in tool_names_raw if isinstance(t, str)]
        if not tool_names:
            return []

        # Get tool definitions from workflow
        tool_defs = getattr(self._workflow_class, "_tools", {})

        # Build tool refs for the tool provider
        tool_refs: list[McpToolRef | StreetraceToolRef] = []

        for tool_name in tool_names:
            tool_def = tool_defs.get(tool_name, {})
            tool_type = tool_def.get("type", "builtin")

            if tool_type == "builtin":
                # Map builtin refs like "streetrace.fs" to StreetRace tools
                builtin_tools = self._get_builtin_tools(tool_name, tool_def)
                tool_refs.extend(builtin_tools)
            elif tool_type == "mcp":
                url = tool_def.get("url", "")
                if url:
                    # Determine transport type from URL
                    transport: HttpTransport | SseTransport
                    if url.endswith("/sse") or "sse" in url.lower():
                        transport = SseTransport(url=url)
                    else:
                        transport = HttpTransport(url=url)
                    tool_refs.append(
                        McpToolRef(
                            name=tool_name,
                            server=transport,
                            tools=["*"],  # Include all tools from this server
                        ),
                    )
            else:
                # Default to builtin
                builtin_tools = self._get_builtin_tools(tool_name, tool_def)
                tool_refs.extend(builtin_tools)

        # Use tool provider to resolve the tool refs
        return tool_provider.get_tools(tool_refs)

    def _get_builtin_tools(
        self,
        tool_name: str,
        tool_def: dict[str, object],
    ) -> list["StreetraceToolRef"]:
        """Get StreetRace tool refs for a builtin tool definition.

        Args:
            tool_name: Name of the tool.
            tool_def: Tool definition dict.

        Returns:
            List of StreetRaceToolRef objects.

        """
        from streetrace.tools.tool_refs import StreetraceToolRef

        # Default fs tools to provide
        fs_tool_functions = [
            "read_file",
            "create_directory",
            "write_file",
            "append_to_file",
            "list_directory",
            "find_in_files",
        ]

        cli_tool_functions = [
            "execute_cli_command",
        ]

        refs: list[StreetraceToolRef] = []

        # Check for specific builtin ref patterns
        builtin_ref = tool_def.get("builtin_ref") or tool_def.get("url")
        if builtin_ref:
            # Handle patterns like "streetrace.fs", "streetrace.cli"
            if "fs" in str(builtin_ref).lower():
                refs.extend(
                    StreetraceToolRef(module="fs_tool", function=func)
                    for func in fs_tool_functions
                )
            elif "cli" in str(builtin_ref).lower():
                refs.extend(
                    StreetraceToolRef(module="cli_tool", function=func)
                    for func in cli_tool_functions
                )
        elif "fs" in tool_name.lower():
            # Infer from tool name
            refs.extend(
                StreetraceToolRef(module="fs_tool", function=func)
                for func in fs_tool_functions
            )
        elif "cli" in tool_name.lower():
            refs.extend(
                StreetraceToolRef(module="cli_tool", function=func)
                for func in cli_tool_functions
            )

        return refs

    async def _create_agent_from_def(
        self,
        name: str,
        agent_def: dict[str, object],
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> "BaseAgent":
        """Create an LlmAgent from an agent definition dict.

        This method is used for creating both the root agent and sub-agents.
        It handles instruction, model, tools resolution and recursively
        resolves nested patterns.

        Args:
            name: Name for the agent.
            agent_def: Agent definition dict with tools, instruction, etc.
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            The created ADK agent.

        """
        from google.adk.agents import LlmAgent

        instruction = self._resolve_instruction(agent_def)
        model = self._resolve_model(model_factory, agent_def)
        tools = self._resolve_tools(tool_provider, agent_def)

        # Recursively resolve nested patterns
        sub_agents = await self._resolve_sub_agents(
            agent_def, model_factory, tool_provider, system_context,
        )
        agent_tools = await self._resolve_agent_tools(
            agent_def, model_factory, tool_provider, system_context,
        )
        tools.extend(agent_tools)

        # Get description from agent definition or use default
        description = agent_def.get("description", f"Agent: {name}")

        agent_kwargs: dict[str, Any] = {
            "name": name,
            "model": model,
            "instruction": instruction,
            "tools": tools,
            "description": description,
        }
        if sub_agents:
            agent_kwargs["sub_agents"] = sub_agents

        return LlmAgent(**agent_kwargs)

    async def _resolve_sub_agents(
        self,
        agent_def: dict[str, object],
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> list["BaseAgent"]:
        """Resolve sub_agents for the coordinator/dispatcher pattern.

        Create LlmAgent instances for each agent listed in 'sub_agents'.
        This enables the delegate keyword functionality where a coordinator
        agent can dispatch work to specialized sub-agents.

        Args:
            agent_def: Agent definition dict.
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            List of created sub-agent instances.

        """
        sub_agent_names = agent_def.get("sub_agents", [])
        if not sub_agent_names or not isinstance(sub_agent_names, list):
            return []

        agents = self._workflow_class._agents  # noqa: SLF001
        sub_agents: list[BaseAgent] = []

        for agent_name in sub_agent_names:
            if not isinstance(agent_name, str):
                continue
            if agent_name not in agents:
                logger.warning("Sub-agent '%s' not found in workflow", agent_name)
                continue

            sub_agent_def = agents[agent_name]
            if not isinstance(sub_agent_def, dict):
                continue

            sub_agent = await self._create_agent_from_def(
                name=agent_name,
                agent_def=sub_agent_def,
                model_factory=model_factory,
                tool_provider=tool_provider,
                system_context=system_context,
            )
            sub_agents.append(sub_agent)

        return sub_agents

    async def _resolve_agent_tools(
        self,
        agent_def: dict[str, object],
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> list["AdkTool"]:
        """Resolve agent_tools for the hierarchical pattern.

        Create AgentTool wrappers for each agent listed in 'agent_tools'.
        This enables the use keyword functionality where an agent can
        invoke other agents as tools.

        Args:
            agent_def: Agent definition dict.
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            List of AgentTool instances.

        """
        from google.adk.tools.agent_tool import AgentTool

        agent_tool_names = agent_def.get("agent_tools", [])
        if not agent_tool_names or not isinstance(agent_tool_names, list):
            return []

        agents = self._workflow_class._agents  # noqa: SLF001
        agent_tools: list[AdkTool] = []

        for agent_name in agent_tool_names:
            if not isinstance(agent_name, str):
                continue
            if agent_name not in agents:
                logger.warning("Agent tool '%s' not found in workflow", agent_name)
                continue

            sub_agent_def = agents[agent_name]
            if not isinstance(sub_agent_def, dict):
                continue

            sub_agent = await self._create_agent_from_def(
                name=agent_name,
                agent_def=sub_agent_def,
                model_factory=model_factory,
                tool_provider=tool_provider,
                system_context=system_context,
            )
            agent_tools.append(AgentTool(sub_agent))

        return agent_tools

    async def close(self, agent_instance: "BaseAgent") -> None:
        """Clean up resources including sub-agents and agent tools.

        Args:
            agent_instance: The root agent instance to close.

        """
        await self._close_agent_recursive(agent_instance)
        self._workflow_instance = None

    async def _close_agent_recursive(self, agent: "BaseAgent") -> None:
        """Recursively close agent, its sub-agents, and tools.

        This method traverses the agent hierarchy depth-first, closing
        sub-agents before parent agents to ensure proper cleanup order.

        Args:
            agent: The agent to close.

        """
        from google.adk.tools.agent_tool import AgentTool

        # Close sub-agents first (depth-first)
        for sub_agent in getattr(agent, "sub_agents", []) or []:
            await self._close_agent_recursive(sub_agent)

        # Close tools, handling AgentTool specially
        for tool in getattr(agent, "tools", []) or []:
            if isinstance(tool, AgentTool):
                # Close the wrapped agent first
                await self._close_agent_recursive(tool.agent)

            # Close the tool itself if it has a close method
            close_fn = getattr(tool, "close", None)
            if callable(close_fn):
                ret = close_fn()
                if inspect.isawaitable(ret):
                    await ret

    def get_attributes(self) -> dict[str, Any]:
        """Get custom attributes for this agent."""
        return {
            "streetrace.agent.type": "dsl",
            "streetrace.agent.source": str(self._source_file),
        }

    def get_version(self) -> str | None:
        """Get the version of this agent."""
        return None

    def get_system_prompt(self) -> str | None:
        """Get the system prompt for this agent."""
        # Get the agent's instruction from the agent definition
        agent_def = self._get_default_agent_def()
        instruction_name = agent_def.get("instruction")
        if instruction_name:
            return f"<prompt: {instruction_name}>"
        return None

    @property
    def user_prompt(self) -> str | None:
        """Get the user prompt for this agent."""
        return None
