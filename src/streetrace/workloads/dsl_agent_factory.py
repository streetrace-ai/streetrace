"""DSL agent factory for creating ADK agents from DSL workflows.

This module provides the DslAgentFactory class that contains the agent creation
logic extracted from DslStreetRaceAgent. It can be used by DslWorkload without
depending on the deprecated DslStreetRaceAgent class.
"""

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.models.base_llm import BaseLlm
    from google.adk.tools.agent_tool import AgentTool

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import AdkTool, ToolProvider
    from streetrace.tools.tool_refs import ToolRef

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)


class DslAgentFactory:
    """Factory for creating ADK agents from DSL workflow definitions.

    This class contains the agent creation logic extracted from DslStreetRaceAgent.
    It can create ADK LlmAgent instances from compiled DSL workflow classes,
    supporting agentic patterns like coordinator (delegate) and hierarchical (use).
    """

    def __init__(
        self,
        workflow_class: type[DslAgentWorkflow],
        source_file: Path | None,
        source_map: list[SourceMapping],
    ) -> None:
        """Initialize the DSL agent factory.

        Args:
            workflow_class: The compiled DSL workflow class.
            source_file: Path to the source .sr file, or None for HTTP sources.
            source_map: Source mappings for error translation.

        """
        self._workflow_class = workflow_class
        self._source_file = source_file
        self._source_map = source_map

        logger.debug(
            "Created DslAgentFactory for %s from %s",
            workflow_class.__name__,
            source_file or "(HTTP source)",
        )

    @property
    def workflow_class(self) -> type[DslAgentWorkflow]:
        """Get the workflow class.

        Returns:
            The compiled DSL workflow class.

        """
        return self._workflow_class

    @property
    def source_file(self) -> Path | None:
        """Get the source file path.

        Returns:
            Path to the source .sr file, or None for HTTP sources.

        """
        return self._source_file

    @property
    def source_map(self) -> list[SourceMapping]:
        """Get the source mappings.

        Returns:
            List of source mappings for error translation.

        """
        return self._source_map

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

        # Look up prompt value
        prompt_value = self._get_prompt_value(instruction_name)
        if prompt_value is None:
            return default_instruction

        # Evaluate the prompt to get the instruction string
        return self._evaluate_prompt(instruction_name, prompt_value)

    def _get_prompt_value(self, instruction_name: str) -> object | None:
        """Get prompt value from workflow prompts dict.

        Args:
            instruction_name: Name of the prompt to look up.

        Returns:
            Prompt value or None if not found.

        """
        if not hasattr(self._workflow_class, "_prompts"):
            logger.warning("No prompts defined in workflow")
            return None

        prompts = self._workflow_class._prompts  # noqa: SLF001
        if instruction_name not in prompts:
            logger.warning("Instruction '%s' not found in prompts", instruction_name)
            return None

        return prompts[instruction_name]

    def _evaluate_prompt(self, instruction_name: str, prompt_value: object) -> str:
        """Evaluate a prompt value to get the instruction string.

        Args:
            instruction_name: Name of the prompt for error logging.
            prompt_value: The prompt value (PromptSpec, callable, or string).

        Returns:
            The evaluated instruction string.

        """
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext
        from streetrace.dsl.runtime.workflow import PromptSpec

        ctx = PromptResolutionContext()

        # Handle PromptSpec objects (new format with escalation support)
        if isinstance(prompt_value, PromptSpec):
            try:
                return str(prompt_value.body(ctx))
            except (TypeError, KeyError) as e:
                logger.warning(
                    "Failed to evaluate prompt '%s': %s", instruction_name, e,
                )
                return ""

        # Handle callable (backward compatibility with old-style lambda prompts)
        if callable(prompt_value):
            try:
                return str(prompt_value(ctx))
            except (TypeError, KeyError) as e:
                logger.warning(
                    "Failed to evaluate prompt '%s': %s", instruction_name, e,
                )
                return ""

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
        from streetrace.dsl.runtime.tool_factory import (
            create_builtin_tool_refs,
            create_mcp_tool_ref,
        )

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
        tool_refs: list[ToolRef] = []

        for tool_name in tool_names:
            tool_def = tool_defs.get(tool_name, {})
            if not isinstance(tool_def, dict):
                tool_def = {}
            tool_type = tool_def.get("type", "builtin")

            if tool_type == "builtin":
                # Map builtin refs like "streetrace.fs" to StreetRace tools
                builtin_tools = create_builtin_tool_refs(tool_name, tool_def)
                tool_refs.extend(builtin_tools)
            elif tool_type == "mcp":
                url = tool_def.get("url", "")
                if url:
                    tool_refs.append(create_mcp_tool_ref(tool_name, tool_def))
            else:
                # Default to builtin
                builtin_tools = create_builtin_tool_refs(tool_name, tool_def)
                tool_refs.extend(builtin_tools)

        # Use tool provider to resolve the tool refs
        return tool_provider.get_tools(tool_refs)

    async def create_agent(
        self,
        agent_name: str,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> "BaseAgent":
        """Create an LlmAgent from an agent definition dict.

        This method is used for creating both the root agent and sub-agents.
        It handles instruction, model, tools resolution and recursively
        resolves nested patterns.

        Args:
            agent_name: Name of the agent to create.
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            The created ADK agent.

        Raises:
            ValueError: If agent not found in workflow.

        """
        from google.adk.agents import LlmAgent

        agents = getattr(self._workflow_class, "_agents", {})
        agent_def = agents.get(agent_name)

        if agent_def is None:
            msg = f"Agent '{agent_name}' not found in workflow"
            raise ValueError(msg)

        if not isinstance(agent_def, dict):
            msg = f"Agent definition for '{agent_name}' is not a dict"
            raise TypeError(msg)

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
        description = agent_def.get("description", f"Agent: {agent_name}")

        agent_kwargs: dict[str, Any] = {
            "name": agent_name,
            "model": model,
            "instruction": instruction,
            "tools": tools,
            "description": description,
        }
        if sub_agents:
            agent_kwargs["sub_agents"] = sub_agents

        return LlmAgent(**agent_kwargs)

    async def create_root_agent(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
    ) -> "BaseAgent":
        """Create the root ADK agent from the DSL workflow.

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

        # Get the agent definition from _agents dict (class-level data)
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
        # Use filename stem or workflow class name for HTTP sources
        if self._source_file:
            agent_name = self._source_file.stem
        else:
            agent_name = self._workflow_class.__name__
        agent_kwargs: dict[str, Any] = {
            "name": agent_name,
            "model": model,
            "instruction": instruction,
            "tools": tools,
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

            sub_agent = await self.create_agent(
                agent_name=agent_name,
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
    ) -> list["AgentTool"]:
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
        agent_tools: list[AgentTool] = []

        for agent_name in agent_tool_names:
            if not isinstance(agent_name, str):
                continue
            if agent_name not in agents:
                logger.warning("Agent tool '%s' not found in workflow", agent_name)
                continue

            sub_agent_def = agents[agent_name]
            if not isinstance(sub_agent_def, dict):
                continue

            sub_agent = await self.create_agent(
                agent_name=agent_name,
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
