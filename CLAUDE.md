# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Build and Quality Checks:**
```bash
# Run all quality checks (tests, linting, type checking, security, dependency check, unused code)
make check

# Individual checks
make test          # Run pytest tests with 5s timeout
make lint          # Run ruff linter
make typed         # Run mypy type checker
make security      # Run bandit security analysis
make depcheck      # Check dependencies with deptry
make unusedcode    # Find unused code with vulture
make coverage      # Generate test coverage report
```

**Development Setup:**
```bash
# Install dependencies
poetry install

# Run the application
poetry run streetrace --model=<provider/model>

# Example: Run with Anthropic Claude
poetry run streetrace --model=anthropic/claude-3-5-sonnet-20241022
```

**Publishing:**
```bash
make publishpatch  # Increment patch version, build, tag, and push (main branch only)
```

## Project Architecture

**Core Application Flow:**
- Entry point: `src/streetrace/main.py` → `create_app()` in `app.py`
- Main orchestrator: `Application` class handles interactive/non-interactive modes
- Input processing pipeline: Commands → Bash → Prompts → Workflow Supervisor

**Key Components:**

1. **Agent System** (`src/streetrace/agents/`):
   - `AgentManager`: Discovers and creates agents from `./agents/` and built-in locations
   - `StreetRaceAgent`: Base interface for creating custom agents
   - Agents require `get_agent_card()`, `get_required_tools()`, `create_agent()` methods

2. **Tool System** (`src/streetrace/tools/`):
   - `ToolProvider`: Manages tool lifecycle and provisioning
   - Tools defined in `./tools/tools.yaml` (local Python modules or MCP services)
   - Built-in tools: file operations, CLI execution, agent discovery

3. **LLM Integration** (`src/streetrace/llm/`):
   - `ModelFactory`: Creates models via LiteLLM
   - Supports multiple providers (Anthropic, OpenAI, Google, Ollama, etc.)
   - Configure with environment variables (`ANTHROPIC_API_KEY`, etc.)

4. **Session Management** (`src/streetrace/session_service.py`):
   - Persistent conversations stored in `.streetrace/sessions/`
   - JSON-based serialization
   - Support for multiple users and apps

5. **UI System** (`src/streetrace/ui/`):
   - `ConsoleUI`: Rich-based terminal interface
   - `UiBus`: Event-driven communication between components
   - Autocompletion for file paths (@-mentions) and commands (/)

6. **Command System** (`src/streetrace/commands/`):
   - Built-in commands: `/help`, `/history`, `/compact`, `/reset`, `/exit`
   - `CommandExecutor` handles command routing and registration

**Project Context:**
- `.streetrace/SYSTEM.md`: System instructions for agents
- `.streetrace/`: Additional context files loaded as conversation messages
- File mentions with @ trigger path autocompletion

**Safety Features:**
- CLI command safety analysis with `bashlex`
- Commands categorized as safe/ambiguous/risky
- Absolute paths and directory traversal attempts blocked by default

**Testing:**
- Uses pytest with asyncio support
- Test structure: `tests/unit/` and `tests/integration/`
- Coverage reports available via `make coverage`

**Code Quality:**
- Ruff for linting (line length: 88)
- MyPy for type checking
- Bandit for security analysis
- Vulture for dead code detection
- All tools configured in `pyproject.toml`

## GitHub Issue Guidelines

- Always use the appropriate issue template from `.github/ISSUE_TEMPLATE/`
- For feature requests: Use `feature_request.md` template with `[IDEA]` title prefix
- For bugs: Use `bug_report.md` template
- Fill out all template sections completely and clearly

## Branch Naming and Workflow

- Follow gitflow naming conventions:
  - Feature branches: `feature/issue-number-short-description` (e.g., `feature/46-github-workflow-integration`)
  - Bugfix branches: `bugfix/issue-number-short-description` (e.g., `bugfix/12-fix-session-loading`)
  - Hotfix branches: `hotfix/issue-number-short-description`
- Always create branches from `main` branch
- Keep branch names lowercase with hyphens as separators

## Commit and PR Guidelines

- ALWAYS reference the issue number in commit messages: `#123: Description of change`
- Use conventional commit format when possible: `type(scope): #123: description`
- Examples:
  - `feat: #46: Add GitHub workflow integration for code review`
  - `fix: #12: Resolve session loading timeout issue`
  - `docs: #15: Update installation instructions`

## ⚠️ CRITICAL: NO AI ATTRIBUTION POLICY

**ABSOLUTELY NEVER add Claude attribution to commits, PRs, or any code contributions.**

This includes:
- ❌ "🤖 Generated with [Claude Code](https://claude.ai/code)"
- ❌ "Co-Authored-By: Claude <noreply@anthropic.com>"
- ❌ Any mention of AI assistance in commit messages
- ❌ Any AI attribution in PR descriptions
- ❌ Any AI-related signatures or footers

**This is a HARD REQUIREMENT. Violations must be immediately corrected.**

When committing changes:
1. Write clean, professional commit messages
2. Focus on WHAT was changed and WHY
3. Never include AI attribution of any kind
4. If attribution is accidentally added, immediately amend the commit to remove it