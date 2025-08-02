"""Code Reviewer Agent implementation.

A specialized agent that reviews ALL file types in pull requests without filtering,
including Python, shell scripts, YAML, JSON, Markdown, and configuration files.
"""

from typing import override

from a2a.types import AgentCapabilities, AgentSkill
from google.adk.agents import Agent, BaseAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool

CODE_REVIEWER_AGENT = """You are a specialized code reviewer for StreetRace🚗💨.

## CRITICAL FIRST STEP

BEFORE doing anything else, you MUST read these files to understand the project:
1. README.md - Read this first to understand what StreetRace is
2. COMPONENTS.md - Read this second to understand the architecture

This is MANDATORY. Do not proceed with any other tasks until you have read both files.

## Your Task

After reading the documentation, conduct a simple code review by:
1. Finding what files have changed using git commands
2. Reviewing the changes for key issues
3. Providing a clear summary of your findings

## Review Focus Areas

Analyze the changes for:
- **Security vulnerabilities**: Exposed secrets, unsafe permissions, injection risks
- **Syntax errors**: Invalid syntax, malformed structures
- **Logic errors**: Incorrect conditionals, wrong file paths, broken references
- **Best practices**: Proper error handling, resource management, maintainability
- **Code quality**: Style consistency, maintainability, performance considerations

## File-Specific Expertise

**Python Files (.py)**:
- Check for security issues (SQL injection, command injection, hardcoded secrets)
- Validate proper error handling and exception management
- Look for performance issues and memory leaks

**Shell Scripts (.sh, .bash, .zsh)**:
- Check for unquoted variables, missing error handling
- Verify proper use of `set -euo pipefail`
- Look for security issues like command injection

**YAML Files (.yml, .yaml)**:
- Validate syntax and structure
- Check for security issues in CI/CD configurations
- Look for hardcoded secrets or sensitive data

**Configuration Files (.json, .toml, .ini, .cfg)**:
- Validate syntax and structure
- Check for security implications of configuration changes
- Verify required fields and proper data types

## Required Output

Save the complete review as a markdown file named "code-review-result.md"

The markdown file should use this format:

```markdown
# Code Review Results

## Summary
- **Files reviewed:** X
- **Issues found:** X errors, X warnings, X notices
- **Overall assessment:** [LGTM/Needs changes/Requires attention]

## Key Findings

### Errors
- Description (filename)

### Warnings  
- Description (filename)

### Notices
- Description (filename)

## Detailed Analysis
[Provide detailed analysis of the changes, security considerations, and recommendations]
```

## Severity Guidelines

- **Error**: Security vulnerabilities, syntax errors, breaking changes
- **Warning**: Best practice violations, potential bugs, performance issues  
- **Notice**: Style suggestions, minor improvements, documentation gaps

## Instructions

1. MANDATORY: Read README.md first using read_file tool
2. MANDATORY: Read COMPONENTS.md second using read_file tool  
3. Only after reading both files, use git commands to find changed files and their differences
4. Review each changed file focusing on the areas above
5. For line numbers, reference git diff hunk headers (e.g., "in hunk starting at line +139") 
6. Avoid specific line numbers unless you read the actual file content to verify them
7. Be thorough but concise in your analysis
8. Use write_file tool to save complete review as markdown file "code-review-result.md"
9. Focus on actionable feedback and prioritize security issues

CRITICAL: After completing the review, you MUST use the write_file tool to save the complete review as "code-review-result.md" in markdown format.
"""


class CodeReviewerAgent(StreetRaceAgent):
    """StreetRace Code Reviewer agent implementation."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        skill = AgentSkill(
            id="comprehensive_code_review",
            name="Comprehensive Code Review",
            description=(
                "Review ALL file types in pull requests without filtering, "
                "including Python, shell scripts, YAML, and configuration files. "
                "Gathers PR context and validates changes against requirements."
            ),
            tags=["code-review", "security", "quality-assurance", "multi-language"],
            examples=[
                "Review all changed files in a PR including Python, shell scripts, "
                "and YAML with full context awareness",
                "Analyze security vulnerabilities across all file types",
                "Check syntax and best practices for configuration files",
                "Validate changes against linked GitHub issues and PR requirements",
            ],
        )

        return StreetRaceAgentCard(
            name="StreetRace_Code_Reviewer_Agent",
            description=(
                "A comprehensive code reviewer that analyzes ALL file types "
                "without filtering and considers PR context and linked issues."
            ),
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    @override
    async def get_required_tools(self) -> list[str | AnyTool]:
        """Provide a list of required tools for code review."""
        return [
            # File system tools for reading and writing files
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::write_file",
            "streetrace:fs_tool::list_directory", 
            "streetrace:fs_tool::find_in_files",
            # CLI tools for git operations
            "streetrace:cli_tool::execute_cli_command",
        ]

    @override
    async def create_agent(
        self,
        model_factory: ModelFactory,
        tools: list[AnyTool],
        system_context: SystemContext,
    ) -> BaseAgent:
        """Create the comprehensive code reviewer agent.

        Args:
            model_factory: Interface to access configured models.
            tools: Tools requested by the agent.
            system_context: System context for the agent.

        Returns:
            The root ADK agent configured for comprehensive code review.

        """
        agent_card = self.get_agent_card()
        return Agent(
            name="StreetRace_Code_Reviewer",
            model=model_factory.get_current_model(),
            description=agent_card.description,
            global_instruction=system_context.get_system_message(),
            instruction=CODE_REVIEWER_AGENT,
            tools=tools,
        )

