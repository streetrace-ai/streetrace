# Workload Examples

This page provides complete, copy-paste ready examples of workloads in DSL, YAML, and
Python formats covering common use cases.

## DSL Examples

### Simple Conversational Agent

A basic agent that responds helpfully to user queries.

**File**: `agents/helper.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt system_prompt:
    You are a helpful assistant. Answer questions clearly and concisely.
    If you don't know something, say so honestly.

agent:
    instruction system_prompt
```

**Run**:
```bash
poetry run streetrace agents/helper.sr "What is the capital of France?"
```

### Agent with Filesystem Tools

An agent that can read and write files in the project directory.

**File**: `agents/file_helper.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.filesystem

prompt file_instruction:
    You are a file management assistant. You can:
    - List files in directories
    - Read file contents
    - Create and modify files

    Always confirm before making changes.

agent:
    tools fs
    instruction file_instruction
```

**Run**:
```bash
poetry run streetrace agents/file_helper.sr "List the Python files in the src directory"
```

### Agent with CLI Access

An agent that can run shell commands safely.

**File**: `agents/cli_helper.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool cli = builtin streetrace.cli

prompt cli_instruction:
    You are a command-line assistant. You can run shell commands to help users.

    Safety guidelines:
    - Never run destructive commands without explicit confirmation
    - Prefer read-only commands when possible
    - Explain what each command does before running it

agent:
    tools cli
    instruction cli_instruction
```

**Run**:
```bash
poetry run streetrace agents/cli_helper.sr "Show me the git status"
```

### Multi-Agent Delegation Pattern

A coordinator agent that delegates to specialized agents.

**File**: `agents/coordinator.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt coordinator_prompt:
    You are a project coordinator. Analyze user requests and delegate to
    the appropriate specialist:

    - For code questions, delegate to the code_expert
    - For documentation questions, delegate to the docs_expert

    Summarize the specialist's response for the user.

prompt code_expert_prompt:
    You are a senior software engineer. Provide detailed, accurate answers
    about code, architecture, and programming best practices.

prompt docs_expert_prompt:
    You are a technical writer. Provide clear, well-structured documentation
    and explanations.

agent coordinator:
    delegate code_expert, docs_expert
    instruction coordinator_prompt

agent code_expert:
    instruction code_expert_prompt

agent docs_expert:
    instruction docs_expert_prompt

flow main:
    $result = run agent coordinator $message
    return $result
```

**Run**:
```bash
poetry run streetrace agents/coordinator.sr "How should I structure a Python package?"
```

### Agent with Tool as Sub-Agent (Use Pattern)

A lead agent that uses another agent as a tool.

**File**: `agents/lead_with_helper.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt lead_prompt:
    You are a lead developer. You have access to a math_helper tool
    that can perform calculations. Use it when needed.

prompt math_helper_prompt:
    You are a math expert. Perform calculations and explain your work.

agent lead:
    use math_helper
    instruction lead_prompt

agent math_helper:
    instruction math_helper_prompt

flow main:
    $result = run agent lead $message
    return $result
```

**Run**:
```bash
poetry run streetrace agents/lead_with_helper.sr "Calculate 15% of 847"
```

### Flow with Conditional Logic

A workflow that processes requests differently based on content.

**File**: `agents/classifier.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt classifier_prompt:
    Classify the user's request into one of these categories:
    - QUESTION: The user is asking a question
    - TASK: The user wants something done
    - CHAT: General conversation

    Respond with only the category name.

prompt question_handler_prompt:
    Answer the user's question helpfully and accurately.

prompt task_handler_prompt:
    Help the user accomplish their task step by step.

prompt chat_handler_prompt:
    Engage in friendly conversation with the user.

agent classifier:
    instruction classifier_prompt

agent question_handler:
    instruction question_handler_prompt

agent task_handler:
    instruction task_handler_prompt

agent chat_handler:
    instruction chat_handler_prompt

flow main:
    $category = run agent classifier $message

    if "QUESTION" in $category:
        $result = run agent question_handler $message
    elif "TASK" in $category:
        $result = run agent task_handler $message
    else:
        $result = run agent chat_handler $message

    return $result
```

**Run**:
```bash
poetry run streetrace agents/classifier.sr "What time is it in Tokyo?"
```

### Agent with Guardrails

An agent with PII masking and jailbreak detection.

**File**: `agents/safe_agent.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt safe_instruction:
    You are a helpful assistant. Respond to user questions appropriately.

agent:
    instruction safe_instruction

flow main:
    # Check for jailbreak attempts
    if guardrails.check("jailbreak", $message):
        return "I cannot help with that request."

    # Mask any PII before processing
    $safe_message = guardrails.mask("pii", $message)

    $result = run agent $safe_message
    return $result
```

**Run**:
```bash
poetry run streetrace agents/safe_agent.sr "My email is test@example.com, can you help?"
```

## YAML Examples

### Basic YAML Agent

A simple declarative agent definition.

**File**: `agents/helper.yaml`

```yaml
name: yaml_helper
description: A helpful YAML-defined assistant
model: anthropic/claude-sonnet
instruction: |
  You are a helpful assistant. Answer questions clearly and concisely.
  If you don't know something, say so honestly.
```

**Run**:
```bash
poetry run streetrace --agent=yaml_helper "Hello!"
```

### YAML Agent with Tools

An agent with access to the filesystem tool.

**File**: `agents/file_agent.yaml`

```yaml
name: yaml_file_agent
description: YAML agent with filesystem access
model: anthropic/claude-sonnet
instruction: |
  You are a file management assistant. You can read and list files.
  Always explain what you're doing.
tools:
  - streetrace.filesystem
```

**Run**:
```bash
poetry run streetrace --agent=yaml_file_agent "List files in current directory"
```

### YAML Agent with Custom Model

An agent using a specific model configuration.

**File**: `agents/custom_model.yaml`

```yaml
name: custom_model_agent
description: Agent using a custom model
model: openai/gpt-4o
instruction: |
  You are an expert assistant using GPT-4o.
  Provide detailed, thoughtful responses.
```

**Run**:
```bash
poetry run streetrace --agent=custom_model_agent "Explain quantum computing"
```

### YAML Agent with Reference

An agent that inherits from another definition.

**File**: `agents/base.yaml`

```yaml
name: base_agent
description: Base agent configuration
model: anthropic/claude-sonnet
instruction: |
  You are a helpful assistant.
```

**File**: `agents/extended.yaml`

```yaml
name: extended_agent
description: Extended agent with additional capabilities
$ref: ./base.yaml
instruction: |
  You are a helpful assistant with expertise in Python programming.
  Build on the base capabilities with specialized knowledge.
```

**Run**:
```bash
poetry run streetrace --agent=extended_agent "How do I use asyncio?"
```

## Python Examples

### Basic Python Agent

A minimal Python agent implementation.

**Directory**: `agents/basic_python/agent.py`

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class BasicPythonAgent(StreetRaceAgent):
    """A basic Python-defined agent."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="basic_python_agent",
            description="A helpful Python-defined assistant",
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_current_model()
        return LlmAgent(
            name="basic_python_agent",
            model=model.model_id,
            instruction="You are a helpful assistant. Be concise and friendly.",
        )
```

**Run**:
```bash
poetry run streetrace --agent=basic_python_agent "Hello!"
```

### Python Agent with Tools

A Python agent that includes filesystem tools.

**Directory**: `agents/python_with_tools/agent.py`

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class PythonToolsAgent(StreetRaceAgent):
    """Python agent with filesystem tools."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="python_tools_agent",
            description="Python agent with file system access",
        )

    async def get_required_tools(self):
        # Request filesystem tools
        return ["streetrace.filesystem"]

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_current_model()

        # Get tools from provider
        tools = await tool_provider.get_tools(["streetrace.filesystem"])

        return LlmAgent(
            name="python_tools_agent",
            model=model.model_id,
            instruction="You are a file management assistant with filesystem access.",
            tools=tools,
        )
```

**Run**:
```bash
poetry run streetrace --agent=python_tools_agent "List Python files"
```

### Python Agent with Custom Logic

A Python agent with preprocessing and postprocessing logic.

**Directory**: `agents/custom_logic/agent.py`

```python
import re
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class CustomLogicAgent(StreetRaceAgent):
    """Python agent with custom preprocessing."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="custom_logic_agent",
            description="Agent with custom preprocessing and postprocessing",
        )

    def _preprocess_message(self, message: str) -> str:
        """Clean and normalize user input."""
        # Remove excess whitespace
        message = re.sub(r"\s+", " ", message).strip()
        # Add context
        return f"[User query, please respond helpfully]: {message}"

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_current_model()

        # Get project-level instructions
        project_instructions = system_context.get_project_instructions()

        instruction = f"""
        You are a helpful assistant.

        Project context:
        {project_instructions}

        Respond clearly and concisely.
        """

        return LlmAgent(
            name="custom_logic_agent",
            model=model.model_id,
            instruction=instruction,
        )
```

**Run**:
```bash
poetry run streetrace --agent=custom_logic_agent "Help me debug this code"
```

### Python Agent with State

A Python agent that maintains state across calls.

**Directory**: `agents/stateful/agent.py`

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class StatefulAgent(StreetRaceAgent):
    """Python agent that tracks interaction count."""

    def __init__(self):
        self._interaction_count = 0

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="stateful_agent",
            description="Agent that maintains state",
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        self._interaction_count += 1
        model = model_factory.get_current_model()

        instruction = f"""
        You are a helpful assistant.
        This is interaction #{self._interaction_count} in this session.
        """

        return LlmAgent(
            name="stateful_agent",
            model=model.model_id,
            instruction=instruction,
        )
```

## Real-World Use Cases

### Code Review Agent

An agent that reviews code and suggests improvements.

**File**: `agents/code_reviewer.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.filesystem

prompt review_prompt:
    You are a senior code reviewer. When reviewing code:

    1. Check for bugs and logic errors
    2. Suggest performance improvements
    3. Identify security vulnerabilities
    4. Recommend better patterns or idioms
    5. Note any missing error handling

    Be constructive and explain your suggestions clearly.

agent:
    tools fs
    instruction review_prompt
```

**Run**:
```bash
poetry run streetrace agents/code_reviewer.sr "Review the file src/main.py"
```

### Documentation Generator

An agent that generates documentation for code.

**File**: `agents/doc_generator.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.filesystem

prompt doc_prompt:
    You are a technical documentation expert. Generate clear, comprehensive
    documentation including:

    - Module overview
    - Function/class descriptions
    - Parameter documentation
    - Usage examples
    - Return value descriptions

    Use proper markdown formatting.

agent:
    tools fs
    instruction doc_prompt
```

**Run**:
```bash
poetry run streetrace agents/doc_generator.sr "Document the module at src/utils.py"
```

### Git Commit Helper

An agent that helps write git commit messages.

**File**: `agents/commit_helper.sr`

```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool cli = builtin streetrace.cli

prompt commit_prompt:
    You are a git commit message expert. Help users write clear, conventional
    commit messages following this format:

    type(scope): subject

    body (optional)

    Types: feat, fix, docs, style, refactor, test, chore

    First, analyze the staged changes using `git diff --staged`, then suggest
    an appropriate commit message.

agent:
    tools cli
    instruction commit_prompt
```

**Run**:
```bash
poetry run streetrace agents/commit_helper.sr "Help me write a commit message"
```

## See Also

- [Getting Started](getting-started.md) - Introduction to workloads
- [Configuration](configuration.md) - Search paths and environment variables
- [DSL Syntax Reference](../dsl/syntax-reference.md) - Complete DSL language reference
- [Multi-Agent Patterns](../dsl/multi-agent-patterns.md) - Delegate and use patterns
