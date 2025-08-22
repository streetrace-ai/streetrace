"""Builder for creating ADK agents from YAML specifications."""

import inspect
from typing import TYPE_CHECKING

from streetrace.agents.yaml_models import (
    AgentRef,
    HttpServerConfig,
    InlineAgentSpec,
    McpToolSpec,
    StdioServerConfig,
    StreetraceToolSpec,
    ToolSpec,
    YamlAgentDocument,
    YamlAgentSpec,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.mcp_transport import HttpTransport, StdioTransport, Transport
from streetrace.tools.tool_provider import AdkTool, AnyTool, ToolProvider
from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.models.base_llm import BaseLlm
from typing import Any

logger = get_logger(__name__)


class YamlAgentBuilder:
    """Builds ADK agents from YAML agent specifications."""

    def __init__(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
    ) -> None:
        """Initialize the builder."""
        self.model_factory = model_factory
        self.tool_provider = tool_provider
        self.system_context = system_context

    def _create_transport_from_server_config(
        self,
        server_config: StdioServerConfig | HttpServerConfig,
    ) -> Transport:
        """Create a transport instance from server configuration."""
        if isinstance(server_config, StdioServerConfig):
            return StdioTransport(
                command=server_config.command,
                args=server_config.args,
                env=server_config.env,
            )
        if isinstance(server_config, HttpServerConfig):
            return HttpTransport(
                url=server_config.url,
                headers=server_config.headers,
                timeout=server_config.timeout,
            )
        msg = f"Unsupported server config type: {type(server_config)}"
        raise ValueError(msg)

    def _convert_tool_spec_to_tool_ref(self, tool_spec: ToolSpec) -> AnyTool:
        """Convert a YAML tool specification to a ToolRef."""
        if tool_spec.streetrace:
            streetrace_spec: StreetraceToolSpec = tool_spec.streetrace
            return StreetraceToolRef(
                module=streetrace_spec.module,
                function=streetrace_spec.function,
            )
        if tool_spec.mcp:
            mcp_spec: McpToolSpec = tool_spec.mcp
            transport = self._create_transport_from_server_config(mcp_spec.server)
            return McpToolRef(
                name=mcp_spec.name,
                server=transport,
                tools=mcp_spec.tools,
            )
        msg = "Tool specification must have either 'streetrace' or 'mcp' field"
        raise ValueError(msg)

    def _create_agent_tools(
        self,
        tools: list[ToolSpec | AgentRef | InlineAgentSpec],
        model: "BaseLlm | None",
    ) -> list["AdkTool"]:
        if not tools:
            return []

        tool_refs: list[AnyTool] = []
        for tool_spec in tools:
            if isinstance(tool_spec, AgentRef):
                msg = "Agent references must be resolved before creating the agent"
                raise TypeError(msg)
            if isinstance(tool_spec, InlineAgentSpec):
                from google.adk.tools.agent_tool import AgentTool

                # Agent-tools typically get a subset of tools or specialized tools
                agent_tool = AgentTool(
                    self._create_agent_from_spec(
                        spec=tool_spec.agent,
                        model=model,
                    ),
                )
                tool_refs.append(agent_tool)
            if isinstance(tool_spec, ToolSpec):
                tool_ref = self._convert_tool_spec_to_tool_ref(tool_spec)
                tool_refs.append(tool_ref)

        return self.tool_provider.get_tools(tool_refs)

    def _create_sub_agents(
        self,
        agents: list[AgentRef | InlineAgentSpec],
        model: "BaseLlm | None",
    ) -> list["BaseAgent"]:
        if not agents:
            return []

        sub_agents = []
        for sub_spec in agents:
            if isinstance(sub_spec, AgentRef):
                msg = "Agent references must be resolved before creating the agent"
                raise TypeError(msg)
            # Each sub-agent gets its own copy of tools
            # In a more sophisticated implementation, we might filter tools
            # based on the sub-agent's own tool specifications
            sub_agent = self._create_agent_from_spec(
                spec=sub_spec.agent,
                model=model,
            )
            sub_agents.append(sub_agent)
        return sub_agents

    def _adk_config(self, spec: YamlAgentSpec) -> dict[str, Any]:
        adk_config = spec.adk
        agent_args: dict[str, Any] = {}
        # Map common ADK fields
        if adk_config.disallow_transfer_to_parent:
            agent_args["disallow_transfer_to_parent"] = (
                adk_config.disallow_transfer_to_parent
            )

        if adk_config.disallow_transfer_to_peers:
            agent_args["disallow_transfer_to_peers"] = (
                adk_config.disallow_transfer_to_peers
            )

        if adk_config.include_contents != "default":
            agent_args["include_contents"] = adk_config.include_contents

        # Handle schema fields (if ADK supports them)
        if adk_config.input_schema:
            # In a real implementation, we'd need to resolve string schema names
            # to actual schema objects
            msg = f"input_schema not implemented yet for agent '{spec.name}'"
            raise NotImplementedError(msg)

        if adk_config.output_schema:
            msg = f"output_schema not implemented yet for agent '{spec.name}'"
            raise NotImplementedError(msg)

        # Pass through any other ADK fields
        if adk_config.model_extra:
            for key, value in adk_config.model_extra.items():
                if key not in agent_args:
                    agent_args[key] = value

        return agent_args

    def _create_agent_from_spec(
        self,
        spec: YamlAgentSpec,
        model: "BaseLlm | None" = None,
        global_instruction: str | None = None,
    ) -> "BaseAgent":
        """Create an ADK agent from specification.

        Args:
            spec: YAML agent specification
            model: Model name to use (inherits if None)
            global_instruction: Global instruction to assign to this agent

        Returns:
            Created ADK agent

        """
        # Prepare ADK constructor arguments
        agent_args: dict[str, Any] = {
            "name": spec.name,
            "description": spec.description,
        }

        # if spec defines a model, use that model
        # else if model is passed, use that model
        # else use system default model
        if spec.model:
            model = self.model_factory.get_llm_interface(
                model_name=spec.model,
            ).get_adk_llm()
        if not model:
            model = self.model_factory.get_current_model()
        agent_args["model"] = model

        tools = self._create_agent_tools(spec.tools, model)
        if tools:
            agent_args["tools"] = tools

        # Create sub-agents if any
        sub_agents = self._create_sub_agents(spec.sub_agents, model)
        if sub_agents:
            agent_args["sub_agents"] = sub_agents

        # Add instruction if provided
        if spec.instruction:
            agent_args["instruction"] = spec.instruction

        # Add global_instruction only for root agent
        if spec.global_instruction:
            agent_args["global_instruction"] = spec.global_instruction
        elif global_instruction:
            # Use system context for global instruction if not explicitly set
            agent_args["global_instruction"] = global_instruction

        agent_args = {**self._adk_config(spec), **agent_args}

        from google.adk.agents import Agent

        return Agent(**agent_args)

    def create_agent(
        self,
        agent_doc: YamlAgentDocument,
    ) -> "BaseAgent":
        """Create an ADK agent from an agent document.

        Args:
            agent_doc: Agent document with resolved specifications
            tools: Available ADK tools

        Returns:
            Created ADK agent

        """
        return self._create_agent_from_spec(
            agent_doc.spec,
            global_instruction=self.system_context.get_system_message(),
        )

    async def close(self, agent: "BaseAgent") -> None:
        """Close agent and all its tools/sub-agents recursively in depth-first order.

        Args:
            agent: The agent to close

        """
        await self._close_agent_recursive(agent)

    async def _close_agent_recursive(self, agent: "BaseAgent") -> None:
        """Recursively close agent, its sub-agents, and tools in depth-first order."""
        # First, recursively close all sub-agents
        for sub_agent in agent.sub_agents:
            await self._close_agent_recursive(sub_agent)

        # Then close all tools, handling AgentTool specially
        # Check if agent has tools (only LlmAgent and its subclasses do)
        for tool in getattr(agent, "tools", []) or []:
            await self._close_tool_recursive(tool)

    async def _close_tool_recursive(self, tool: object) -> None:
        """Recursively close a tool, handling AgentTool specially."""
        # If this is an AgentTool, traverse its agent first before closing the tool
        from google.adk.tools.agent_tool import AgentTool

        if isinstance(tool, AgentTool):
            await self._close_agent_recursive(tool.agent)

        # Then close the tool itself if it has a close method
        close_fn = getattr(tool, "close", None)
        if callable(close_fn):
            ret = close_fn()
            if inspect.isawaitable(ret):
                await ret
