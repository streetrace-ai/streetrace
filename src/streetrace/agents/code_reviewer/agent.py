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

## CRITICAL FIRST STEPS

BEFORE doing anything else, you MUST:
1. Read README.md - Understand what StreetRace is
2. Read COMPONENTS.md - Understand the architecture
3. Check for PR context using `gh pr view --json` to get PR description and related issues
   - If `gh` commands fail due to authentication, continue without PR context
4. If GitHub issues are referenced, use `gh issue view <number>` to understand requirements

This context is MANDATORY for providing relevant, scope-aware code reviews.

## Your Task

After reading the documentation and understanding the PR context:
1. Find what files have changed using proper PR diff commands:
   - Use `git diff origin/main...HEAD` to get the full PR diff against main branch
   - If origin/main is not available, use `git diff main...HEAD` or `git merge-base main HEAD` and `git diff $(git merge-base main HEAD)...HEAD`
   - Use `git diff --name-only origin/main...HEAD` to list changed files
   - NEVER use `git diff HEAD HEAD~1` as it only shows the last commit
2. Review the changes against the PR description and issue requirements
3. Analyze scope: what was implemented vs what was requested
4. Provide findings with context about completeness and scope

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

CRITICAL: You MUST save the complete review as a markdown file named
"code-review-result.md"
DO NOT print the review to console - ONLY save it to the file using write_file tool.

The markdown file should use this format with scope analysis:

```markdown
# Code Review Results

## Summary
- **Files reviewed:** X
- **Issues found:** X errors, X warnings, X notices
- **Overall assessment:** [LGTM/Needs changes/Requires attention]
- **Scope assessment:** [Complete/Missing features/Beyond scope]

## Scope Analysis
### Requirements Met
- [List implemented features that match PR description/issues]

### Potential Gaps
- [Features mentioned in PR/issues but not clearly implemented]

### Beyond Scope
- [Features implemented that weren't explicitly requested]

## Key Findings

### Errors
- Description (filename)

### Warnings
- Description (filename)

### Notices
- Description (filename)

## Detailed Analysis
[Provide detailed analysis of changes, security considerations, and scope completeness]
```

## Severity Guidelines

- **Error**: Security vulnerabilities, syntax errors, breaking changes
- **Warning**: Best practice violations, potential bugs, performance issues
- **Notice**: Style suggestions, minor improvements, documentation gaps

## Instructions

1. MANDATORY: Read README.md first using read_file tool
2. MANDATORY: Read COMPONENTS.md second using read_file tool
3. MANDATORY: Use `gh pr view --json` to get PR description and related issues
4. MANDATORY: If issues referenced, use `gh issue view <number>` for requirements
5. Use git commands to find changed files and diffs:
   - `git diff origin/main...HEAD` for full PR diff
   - `git diff --name-only origin/main...HEAD` for changed files list
   - Fallback to `git diff main...HEAD` if origin/main unavailable
6. Review changes against PR description and issue requirements
7. Analyze scope: implemented vs requested vs beyond scope
8. For line numbers, reference git diff hunk headers (e.g., "in hunk starting at +139")
9. Be thorough but concise in analysis with scope context
10. Use write_file tool to save complete review as markdown file
    "code-review-result.md"
11. Focus on actionable feedback, security issues, and scope completeness

CRITICAL REQUIREMENTS:
- You MUST use the write_file tool to save the complete review as
  "code-review-result.md"
- DO NOT print the review content to console - file saving is MANDATORY
- The review should ONLY exist in the file, not in console output
- After saving, use read_file to verify the file exists and contains your review
- Only after verification, confirm that the file was created successfully
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
            # CLI tools for git and GitHub operations (git, gh commands)
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

