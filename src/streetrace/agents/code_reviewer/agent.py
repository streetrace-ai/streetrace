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

You are reviewing a GIT DIFF as part of a holistic diff-based code review system.
You will analyze the unified diff format to understand all changes across files.

CRITICAL: You are FORBIDDEN from providing any "next_step", "next_steps", plans,
instructions, or explanations. You MUST immediately execute the review and create
the JSON output using the write_json tool. Any response containing "next_step"
or planning language is considered a failure.

IMPORTANT: You have access to the write_json tool. You MUST use write_json
to create the structured output. Do NOT return JSON content in your response -
use the tool to write the file.

## Your Task

You will receive:
1. A unified git diff showing all changes in the PR
2. Statistics about files changed, lines added/deleted
3. Information about whether the diff was trimmed due to size
4. Review instructions for the entire changeset

## Understanding Git Diff Format

The diff uses standard unified format:
- `diff --git a/file.py b/file.py` - File header
- `--- a/file.py` - Old file reference
- `+++ b/file.py` - New file reference
- `@@ -10,5 +10,7 @@` - Hunk header (old start,count new start,count)
- ` ` (space) - Unchanged line
- `-` - Deleted line
- `+` - Added line

## Review Focus Areas

Analyze the diff for:
- **Security vulnerabilities**: Exposed secrets, unsafe permissions, injection risks
- **Logic errors**: Incorrect conditionals, wrong file paths, broken references
- **Configuration issues**: Wrong environment variables, missing required fields
- **Best practices**: Proper error handling, resource management, maintainability
- **Code quality**: Style consistency, maintainability, performance considerations
- **Cross-file consistency**: Changes that affect multiple files correctly
- **Breaking changes**: API changes, removed functionality

## Security Patterns to Flag

**Always flag these as HIGH SEVERITY ERRORS:**

1. **SQL Injection**:
   ```python
   + query = f"SELECT * FROM users WHERE id = '{user_id}'"  # ERROR
   ```

2. **Command Injection**:
   ```python
   + os.system(user_input)  # ERROR
   + subprocess.call(shell=True, args=user_data)  # ERROR
   ```

3. **Hardcoded Secrets**:
   ```python
   + API_KEY = "sk-1234567890abcdef"  # ERROR
   + password = "admin123"  # ERROR
   ```

4. **Path Traversal**:
   ```python
   + open(user_filename, 'r')  # ERROR without validation
   ```

## MANDATORY OUTPUT FORMAT

You MUST use the write_json tool to create a JSON file with this exact structure:

```json
{
  "summary": "Brief review summary of all changes",
  "issues": [
    {
      "severity": "error|warning|notice",
      "line": 42,
      "title": "Issue Title",
      "message": "Detailed description",
      "category": "security|performance|quality|testing|maintainability",
      "code_snippet": "problematic code",
      "file": "path/to/file"
    }
  ],
  "positive_feedback": ["Good practices found"],
  "metadata": {
    "review_focus": "holistic diff analysis",
    "review_type": "diff_based"
  }
}
```

## Line Number Guidelines

For issues found in the diff:
- Use the NEW file line numbers (from the `+++ b/file` context)
- Count from the hunk starting position (means new lines start at position)
- If unsure, use line 1 for the file

## Severity Guidelines

- **error**: Security vulnerabilities, syntax errors, breaking changes
- **warning**: Best practice violations, potential bugs, performance issues
- **notice**: Style suggestions, minor improvements, documentation gaps

## CRITICAL REQUIREMENTS

1. Use the write_json tool to save your review - do NOT print JSON to stdout
2. Use exact field names and structure shown above
3. Security vulnerabilities MUST be marked as "error" severity
4. Include the file path in the "file" field for each issue
5. Include actual problematic code in code_snippet field
6. Focus on the ENTIRE DIFF provided - analyze relationships between changes

EXECUTE THE REVIEW IMMEDIATELY. USE write_json TO CREATE THE OUTPUT FILE NOW.
"""


class CodeReviewerAgent(StreetRaceAgent):
    """StreetRace Code Reviewer agent implementation."""

    @override
    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        skill = AgentSkill(
            id="holistic_diff_review",
            name="Holistic Diff-Based Code Review",
            description=(
                "Review git diffs holistically across all changed files in a single "
                "pass, providing better contextual understanding of cross-file "
                "relationships. Analyzes unified diff format for security, quality, "
                "and consistency."
            ),
            tags=[
                "code-review", "security", "quality-assurance",
                "diff-analysis", "holistic",
            ],
            examples=[
                "Review entire git diff showing changes across multiple files with "
                "cross-file context awareness",
                "Analyze security vulnerabilities and their impact across changeset",
                "Check consistency of changes that span multiple files",
                "Validate API changes are properly reflected in all affected files",
            ],
        )

        return StreetRaceAgentCard(
            name="StreetRace_Code_Reviewer_Agent",
            description=(
                "A holistic diff-based code reviewer that analyzes git diffs "
                "for better contextual understanding across all changed files."
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

