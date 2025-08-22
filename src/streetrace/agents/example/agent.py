"""Hello World Agent implementation.

A simple example agent that demonstrates the basic structure of a StreetRace agent.
"""

import os
from typing import TYPE_CHECKING, override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.mcp_transport import HttpTransport, StdioTransport
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.tools.tool_refs import (
    McpToolRef,
    StreetraceToolRef,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

GENERIC_AGENT = """You are StreetRace🚗💨, a helpful assistant that helps the user with
their daily tasks.

When the user asks something, understand their final goal, ask clarifyign questions if
necessary, and use the provided tools to reach user's goal.
"""

GITHUB_PERSONAL_ACCESS_TOKEN = (
    os.environ.get("GITHUB_TOKEN")
    or os.environ.get(
        "GITHUB_PERSONAL_ACCESS_TOKEN",
    )
    or os.environ.get("GITHUB_PAT")
)


class GenericAgent(StreetRaceAgent):
    """StreetRace Coder agent implementation."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        skill = AgentSkill(
            id="help_user",
            name="Help User",
            description="Analyze the requirements and implement a feature in code.",
            tags=["help"],
            examples=["Help me book tickets to Atlanta."],
        )

        return StreetRaceAgentCard(
            name="generic",
            description="A helpful assistant who works with you to reach your goals.",
            version="0.2.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[AnyTool]:
        """Provide a list of required tool references using structured ToolRef objects.

        Returns structured tool references instead of string-based tool names.
        """
        tools: Sequence[AnyTool] = [
            # StreetRace internal tools for file system operations
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="fs_tool", function="create_directory"),
            StreetraceToolRef(module="fs_tool", function="write_file"),
            StreetraceToolRef(module="fs_tool", function="append_to_file"),
            StreetraceToolRef(module="fs_tool", function="list_directory"),
            StreetraceToolRef(module="fs_tool", function="find_in_files"),
            # MCP filesystem server tools for advanced file operations
            McpToolRef(
                name="filesystem",
                server=StdioTransport(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem"],
                ),
                tools=[
                    "edit_file",
                    "move_file",
                    "get_file_info",
                    "list_allowed_directories",
                ],
            ),
            McpToolRef(
                name="github",
                server=HttpTransport(
                    url="https://api.githubcopilot.com/mcp/",
                    headers={
                        "Authorization": f"Bearer {GITHUB_PERSONAL_ACCESS_TOKEN}",
                    },
                    timeout=10,
                ),
            ),
            McpToolRef(
                name="context7",
                server=HttpTransport(
                    url="https://mcp.context7.com/mcp",
                    timeout=10,
                ),
            ),
            # CLI tool for command execution
            StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
        ]
        return list(tools)

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the agent Run the Hello World agent with the provided input.

        Args:
            model_factory: Interface to access configured models.
            tool_provider: Tool provider.
            system_context: System context for the agent.

        Returns:
            The root ADK agent.

        """
        agent_card = self.get_agent_card()
        return Agent(
            name=agent_card.name,
            model=model_factory.get_current_model(),
            description=agent_card.description,
            global_instruction=system_context.get_system_message(),
            instruction=GENERIC_AGENT,
            tools=tool_provider.get_tools(await self.get_required_tools()),
            sub_agents=[],
        )
