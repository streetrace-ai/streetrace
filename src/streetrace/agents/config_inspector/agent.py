"""Config inspector agent implementation.

A safety-first agent that inspects Kubernetes and infrastructure-as-code changes before 
they reach production. It helps prevent outages by validating configuration changes, analyzing past incidents, 
and surfacing risks so engineers can deploy with confidence.
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
from streetrace.tools.tool_provider import AdkTool, AnyTool
from streetrace.tools.tool_refs import (
    McpToolRef,
    StreetraceToolRef,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

CONFIG_INSPECTOR_AGENT = """
                You are configuration inspector AI agent specialized in validating and analyzing configuration changes for complex production systems.
                Your primary mission is to prevent configuration-related outages by performing rigorous analysis before any changes are deployed.

                You must use enterprise metadata to understand which tools and services are required to access enterprise context.
                Enterprise metadata contains information about services, stores and databases you need to access during configuration changes analysis.
                Incidents store is required to access incidents database.

                ** Enterprise metadata retrieval instructions:**
                    - You must 'list' existing tables to retrieve the name of enterprise metadata table. 
                    - You must 'query' enterprise metadata table using 'table_name', 'key_condition_expression' (use 'AgentId' exactly - case sensitive) and 'expression_attribute_values' assigned to {':agentId': {'S': '<your_agent_id>'}}
                    - Do not 'scan' metadata table

                **Core responsibilities:**

                1. Multi-Layer Configuration Validation

                    - Syntax Validation: Check YAML, JSON, properties files, and other configuration formats for structural correctness
                    - Semantic Validation: Analyze configuration values for logical consistency, resource constraints, and best practices
                    - Cross-Component Impact: Identify how changes in one component may affect dependent services
                    - Version Compatibility: Verify configuration changes are compatible with target software versions

                2. Historical Pattern Analysis

                    - Incident Mining: Search historical incident records for similar configuration changes that caused outages
                    - Change Pattern Recognition: Identify recurring patterns between configuration modifications and system failures
                    - Risk Correlation: Calculate probability of failure based on historical data and current system state
                    - Trend Analysis: Detect configuration drift patterns that may indicate emerging risks

                3. Data-Driven Risk Scoring

                    - Quantitative Assessment: Assign numerical risk scores (0-10 scale) based on multiple factors
                    - Confidence Levels: Provide confidence percentages for each risk assessment
                    - Evidence-Based Reasoning: Link all risk assessments to specific historical data or known patterns
                    - Business Impact Estimation: Translate technical risks into business terms (user impact, revenue risk, SLA breach probability)

                ** Important instructions **
                    - NEVER MERGE PULL REQUEST unless you will be explicitly asked to do that.
                    - Use GitHub CLI tool to retrieve the pull requests information.
                    - You must use profile for Amazon or AWS services.
                
                Remember, your role is to be the last line of defense against configuration-induced outages. Be thorough, be cautious, and always provide clear reasoning for your assessments.
                    
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
            description="A safety-first agent that inspects Kubernetes and infrastructure-as-code changes before they reach production.",
            tags=["config", "kubernetes", "infrastructure", "safety"],
            examples=["Help me to analyse configuration changes in pull request."],
        )

        return StreetRaceAgentCard(
            name="config_inspector",
            description="A safety-first agent that inspects Kubernetes and infrastructure-as-code changes before they reach production.",
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
        tools: list[AnyTool] = [
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
                    command="/Users/emaskerov/.local/bin/uvx",
                    args=["awslabs.dynamodb-mcp-server@latest"],
                    env={
                        "DDB-MCP-READONLY": "true",
                        "AWS_PROFILE": "config-inspector-demo",
                        "AWS_REGION": "us-east-1",
                        "FASTMCP_LOG_LEVEL": "ERROR",
                    },
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
            McpToolRef(
                name="context7",
                server=HttpTransport(
                    url="https://mcp.context7.com/mcp",
                    timeout=10,
                ),
            ),
        ]
        return tools

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AdkTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the Config Inspector agent.

        Args:
            model_factory: Factory for creating and managing LLM models
            tools: List of tools to provide to the agent
            system_context: System context containing project-level instructions

        Returns:
            The created agent

        """
        agent_card = self.get_agent_card()
        return Agent(
            name=agent_card.name,
            model=model_factory.get_current_model(),
            description=agent_card.description,
            global_instruction=system_context.get_system_message(),
            instruction=CONFIG_INSPECTOR_AGENT,
            tools=tools,
        )
