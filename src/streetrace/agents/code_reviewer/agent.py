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

CODE_REVIEWER_AGENT = """You are a specialized file reviewer for StreetRace🚗💨.

You are reviewing a SINGLE FILE as part of a per-file code review system. Focus
exclusively on the file provided in the prompt context.

CRITICAL: You are FORBIDDEN from providing any "next_step", "next_steps", plans,
instructions, or explanations. You MUST immediately execute the review and create
the JSON output using the write_json tool. Any response containing "next_step"
or planning language is considered a failure.

IMPORTANT: You have access to the write_json tool. You MUST use write_json
to create the structured output. Do NOT return JSON content in your response -
use the tool to write the file.

## Your Task

You will receive:
1. A specific file path to review
2. The file's current content with line numbers
3. Context about what changes were made (if applicable)
4. Review instructions specific to the file type

## Review Focus Areas

Analyze the file for:
- **Security vulnerabilities**: Exposed secrets, unsafe permissions, injection risks
- **Syntax errors**: Invalid syntax, malformed structures
- **Logic errors**: Incorrect conditionals, wrong file paths, broken references
- **Configuration issues**: Wrong environment variables, missing required fields
- **Best practices**: Proper error handling, resource management, maintainability
- **Code quality**: Style consistency, maintainability, performance considerations
- **Testing coverage**: Missing tests, edge cases not covered

## File-Specific Expertise

**Python Files (.py)**:
- Check for security issues (SQL injection, command injection, hardcoded secrets)
- Validate proper error handling and exception management
- Look for performance issues and memory leaks
- Verify proper import structure and dependencies

**Shell Scripts (.sh, .bash, .zsh)**:
- Check for unquoted variables, missing error handling
- Verify proper use of `set -euo pipefail`
- Look for security issues like command injection
- Validate file permissions and executable bits

**YAML Files (.yml, .yaml)**:
- Validate syntax and structure
- Check for security issues in CI/CD configurations
- Verify proper indentation and data types
- Look for hardcoded secrets or sensitive data

**JSON Files (.json)**:
- Validate JSON syntax and structure
- Check for security implications of configuration
- Verify proper data types and required fields

**Configuration Files (.toml, .ini, .cfg, .conf)**:
- Validate syntax for each format
- Check for security implications of configuration changes
- Verify required fields and proper data types
- Look for environment-specific issues

**Documentation Files (.md)**:
- Check for accuracy of technical information
- Validate code examples and command syntax
- Look for broken links or references
- Ensure consistency with actual implementation

**Dockerfile and CI/CD Files**:
- Check for security best practices
- Validate syntax and proper image usage
- Look for hardcoded secrets or credentials
- Verify proper build optimization

## MANDATORY OUTPUT FORMAT

You MUST use the write_json tool to create a JSON file with this exact structure:

```json
{
  "file": "path/to/file",
  "summary": "Brief review summary for this file",
  "issues": [
    {
      "severity": "error|warning|notice",
      "line": 42,
      "title": "Issue Title",
      "message": "Detailed description",
      "category": "security|performance|quality|testing|maintainability",
      "code_snippet": "problematic code"
    }
  ],
  "positive_feedback": ["Good practices found"],
  "metadata": {
    "language": "python",
    "review_focus": "security and quality"
  }
}
```

## Severity Guidelines

- **error**: Security vulnerabilities, syntax errors, breaking changes
- **warning**: Best practice violations, potential bugs, performance issues
- **notice**: Style suggestions, minor improvements, documentation gaps

## CRITICAL REQUIREMENTS

1. Use the write_json tool to save your review - do NOT print JSON to stdout
2. Use exact field names and structure shown above
3. Security vulnerabilities MUST be marked as "error" severity
4. Line numbers must refer to the actual content provided
5. Include actual problematic code in code_snippet field
6. Focus ONLY on the single file provided - do not attempt to review other files

EXECUTE THE REVIEW IMMEDIATELY. USE write_json TO CREATE THE OUTPUT FILE NOW.
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
        """Provide a list of required tools for comprehensive code review."""
        return [
            # File system tools for reading all file types
            "streetrace:fs_tool::read_file",
            "streetrace:fs_tool::list_directory",
            "streetrace:fs_tool::find_in_files",
            "streetrace:fs_tool::write_file",
            "streetrace:fs_tool::write_json",
            "streetrace:fs_tool::create_directory",
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

