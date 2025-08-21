"""Builder for creating ADK agents from YAML specifications."""


from google.adk.agents import Agent, BaseAgent

from streetrace.agents.yaml_models import (
    AgentDocument,
    HttpServerConfig,
    InlineAgentSpec,
    McpToolSpec,
    StdioServerConfig,
    StreetraceToolSpec,
    ToolSpec,
    YamlAgentSpec,
)
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.mcp_transport import HttpTransport, StdioTransport, Transport
from streetrace.tools.tool_provider import AdkTool, AnyTool
from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef

logger = get_logger(__name__)


class YamlAgentBuilder:
    """Builds ADK agents from YAML agent specifications."""

    def __init__(
        self,
        model_factory: ModelFactory,
        system_context: SystemContext,
    ) -> None:
        """Initialize the builder.

        Args:
            model_factory: Factory for creating and managing LLM models
            system_context: System context containing project-level instructions

        """
        self.model_factory = model_factory
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

    def get_required_tools(self, spec: YamlAgentSpec) -> list[AnyTool]:
        """Extract required tools from agent specification.

        Args:
            spec: YAML agent specification

        Returns:
            List of tool references

        """
        tool_refs: list[AnyTool] = []

        # Convert direct tools
        for tool_spec in spec.tools:
            tool_ref = self._convert_tool_spec_to_tool_ref(tool_spec)
            tool_refs.append(tool_ref)

        # Note: sub_agents and agent_tools don't contribute to tool_refs
        # as they are handled differently in ADK

        return tool_refs

    def _create_sub_agents(
        self,
        sub_agent_specs: list[InlineAgentSpec],
        tools: list[AdkTool],
        model_name: str | None = None,
    ) -> list[BaseAgent]:
        """Create sub-agents from specifications.

        Args:
            sub_agent_specs: List of sub-agent specifications
            tools: Available tools to distribute to sub-agents
            model_name: Model name to use (inherits from parent if None)

        Returns:
            List of created ADK agents

        """
        sub_agents = []

        for sub_agent_spec in sub_agent_specs:
            # Each sub-agent gets its own copy of tools
            # In a more sophisticated implementation, we might filter tools
            # based on the sub-agent's own tool specifications
            sub_agent = self._create_agent_from_spec(
                sub_agent_spec.inline,
                tools,
                model_name=model_name,
                is_root=False,
            )
            sub_agents.append(sub_agent)

        return sub_agents

    def _create_agent_tools(
        self,
        agent_tool_specs: list[InlineAgentSpec],
        tools: list[AdkTool],
        model_name: str | None = None,
    ) -> list[BaseAgent]:
        """Create agent-as-tool instances from specifications.

        Args:
            agent_tool_specs: List of agent-tool specifications
            tools: Available tools to distribute to agent-tools
            model_name: Model name to use (inherits from parent if None)

        Returns:
            List of created ADK agents configured as tools

        """
        agent_tools = []

        for agent_tool_spec in agent_tool_specs:
            # Agent-tools typically get a subset of tools or specialized tools
            agent_tool = self._create_agent_from_spec(
                agent_tool_spec.inline,
                tools,
                model_name=model_name,
                is_root=False,
            )
            agent_tools.append(agent_tool)

        return agent_tools

    def _create_agent_from_spec(
        self,
        spec: YamlAgentSpec,
        tools: list[AdkTool],
        model_name: str | None = None,
        is_root: bool = True,
    ) -> BaseAgent:
        """Create an ADK agent from specification.

        Args:
            spec: YAML agent specification
            tools: Available ADK tools
            model_name: Model name to use (inherits if None)
            is_root: Whether this is the root agent

        Returns:
            Created ADK agent

        """
        # Determine model to use
        effective_model_name = spec.model or model_name
        if effective_model_name:
            model = self.model_factory.get_model(effective_model_name)
        else:
            model = self.model_factory.get_current_model()

        # Create sub-agents if any
        sub_agents = []
        if spec.sub_agents:
            sub_agents = self._create_sub_agents(
                spec.sub_agents,
                tools,
                model_name=effective_model_name,
            )

        # Create agent-tools if any
        agent_tools = []
        if spec.agent_tools:
            agent_tools = self._create_agent_tools(
                spec.agent_tools,
                tools,
                model_name=effective_model_name,
            )

        # Prepare ADK constructor arguments
        agent_args = {
            "name": spec.name,
            "model": model,
            "description": spec.description,
            "tools": tools,
        }

        # Add instruction if provided
        if spec.instruction:
            agent_args["instruction"] = spec.instruction

        # Add global_instruction only for root agent
        if is_root and spec.global_instruction:
            agent_args["global_instruction"] = spec.global_instruction
        elif is_root:
            # Use system context for global instruction if not explicitly set
            agent_args["global_instruction"] = self.system_context.get_system_message()

        # Add sub-agents if any
        if sub_agents:
            agent_args["agents"] = sub_agents

        # Add agent-tools if any (these become regular tools in ADK)
        if agent_tools:
            # In ADK, agent-tools are treated as regular tools
            # We would need to wrap them appropriately here
            # For now, we'll log and skip this feature
            logger.warning(
                "Agent-tools not fully implemented yet for agent '%s'",
                spec.name,
            )

        # Pass through ADK-specific configuration
        adk_config = spec.adk

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
            logger.warning(
                "input_schema not fully implemented yet for agent '%s'",
                spec.name,
            )

        if adk_config.output_schema:
            logger.warning(
                "output_schema not fully implemented yet for agent '%s'",
                spec.name,
            )

        # Pass through any other ADK fields
        for key, value in adk_config.model_extra.items():
            if key not in agent_args:
                agent_args[key] = value

        return Agent(**agent_args)

    def create_agent(self, agent_doc: AgentDocument, tools: list[AdkTool]) -> BaseAgent:
        """Create an ADK agent from an agent document.

        Args:
            agent_doc: Agent document with resolved specifications
            tools: Available ADK tools

        Returns:
            Created ADK agent

        """
        return self._create_agent_from_spec(
            agent_doc.spec,
            tools,
            is_root=True,
        )
