"""Config inspector agent implementation.

A safety-first agent that inspects Kubernetes and infrastructure-as-code changes before
they reach production. It helps prevent outages by validating configuration changes,
analyzing past incidents, and surfacing risks so engineers can deploy with confidence.
"""

import os
from typing import TYPE_CHECKING, override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.mcp_transport import StdioTransport
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.tools.tool_refs import (
    McpToolRef,
    StreetraceToolRef,
)

# Get with default value
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")

if TYPE_CHECKING:
    from collections.abc import Sequence

CONFIG_INSPECTOR_AGENT = """
You are a Configuration Inspector Agent that prevents production outages by analyzing
configuration changes before deployment.

# ROLE
Your mission is to validate configuration changes and identify risks using historical
data and enterprise context.

# TONE
Use formal technical and business tone.

# WORKFLOW
## 1. Enterprise Context Metadata Setup
- List tables to find enterprise metadata table
- Query metadata using: table_name, key_condition_expression='AgentId' (case-sensitive),
expression_attribute_values={':agentId': {'S': '<agent_id>'}}

## 2. Configuration Analysis
Perform these validations in order:

### Syntax Validation
- Check YAML/JSON/properties files for structural correctness and run syntax validation

### Semantic Validation
- Verify logical consistency of configuration values
- Check resource constraints and limits
- Validate against best practices

### Impact Assessment
- Identify cross-component dependencies
- Check version compatibility
- Map potential failure points

## 3. Historical Risk Analysis
- Search incident records for similar changes
- Identify failure patterns in configuration modifications
- Calculate risk probability from historical data
- Detect configuration drift trends

## 4. Risk Scoring & Reporting
Provide structured output:
- Risk score (0-10 scale) with confidence percentage
- Evidence-based reasoning linking to historical data
- Business impact assessment (user/revenue/SLA impact)
- Specific recommendations for risk mitigation

# TOOLS
- Use GitHub CLI tool to retrieve the pull requests information.
- Use 'yamllint' or 'jsonlint' tools for syntax validation when required.
- Use 'context7' tool to retrieve relevant documentation and best practices.
- Use tool from enterprise metadata to retrieve relevant incidents.

# CONSTRAINTS
- Base analysis ONLY on retrieved tool context
- Always execute all 4 stages of workflow
- Provide clear reasoning for all assessments
- Be thorough and cautious in risk evaluation
- When using documentation and best practices add citations and refernces

# OUTPUT
The output format must be in MARKDOWN format.
"""

GITHUB_PERSONAL_ACCESS_TOKEN = (
    os.environ.get("GITHUB_TOKEN")
    or os.environ.get(
        "GITHUB_PERSONAL_ACCESS_TOKEN",
    )
    or os.environ.get("GITHUB_PAT")
)


class ConfigInspectorAgent(StreetRaceAgent):
    """Config inspector agent that implements the StreetRaceAgent interface."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        skill = AgentSkill(
            id="config_inspector",
            name="Config Inspector",
            description="""A safety-first agent that inspects Kubernetes and
                        infrastructure-as-code changes before they reach production.""",
            tags=["config", "kubernetes", "infrastructure", "safety"],
            examples=["Help me to analyse configuration changes in pull request."],
        )

        return StreetRaceAgentCard(
            name="config_inspector",
            description="""A safety-first agent that inspects Kubernetes and
                        infrastructure-as-code changes before they reach production.""",
            version="0.2.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[AnyTool]:
        """Provide a list of required tool references using structured ToolRef objects.

        Returns structured tool references for config inspection capabilities.
        """
        tools: Sequence[AnyTool] = [
            # File system tools for reading and writing configuration files
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="fs_tool", function="write_file"),
            StreetraceToolRef(module="fs_tool", function="list_directory"),
            StreetraceToolRef(module="fs_tool", function="find_in_files"),
            # CLI tools for git and GitHub operations
            StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
            # Kendra tool for incident mining and historical analysis
            StreetraceToolRef(module="kendra_tool", function="kendra_query"),
            McpToolRef(
                name="enterprise-context",
                server=StdioTransport(
                    command="uvx",
                    args=["awslabs.dynamodb-mcp-server@latest"],
                    env={
                        "DDB-MCP-READONLY": "true",
                        "AWS_PROFILE": AWS_PROFILE,
                        "AWS_REGION": AWS_REGION,
                        "FASTMCP_LOG_LEVEL": "ERROR",
                    },
                    timeout=120,
                ),
                tools=[
                    "list_tables",
                    "get_item",
                    "query",
                    "scan",
                ],
            ),
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
        ]
        return list(tools)

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the Config Inspector agent.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider for managing and accessing tools
            system_context: System context containing project-level instructions

        Returns:
            The created agent

        """
        agent_card = self.get_agent_card()
        return Agent(
            name=agent_card.name,
            model=model_factory.get_current_model(),
            description=agent_card.description,
            instruction=CONFIG_INSPECTOR_AGENT,
            tools=tool_provider.get_tools(await self.get_required_tools()),
        )
