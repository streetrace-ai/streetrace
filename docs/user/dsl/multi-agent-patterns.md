# Multi-Agent Patterns

The Streetrace DSL supports multi-agent patterns that let you build sophisticated AI
workflows. This guide explains when and how to use `delegate`, `use`, and `loop` to
coordinate multiple agents.

## Overview

Multi-agent patterns solve different coordination problems:

| Pattern | Keyword | When to Use |
|---------|---------|-------------|
| Coordinator | `delegate` | Route requests to specialists |
| Hierarchical | `use` | Call agents as tools |
| Iterative | `loop` | Repeat until quality threshold |

## Coordinator Pattern (delegate)

The coordinator pattern routes user requests to specialized agents. The coordinator's
LLM decides which specialist should handle each request.

At runtime, agents listed in `delegate` become ADK sub-agents. The coordinator agent
receives the user request and decides which sub-agent should handle it based on its
instruction. Sub-agents share the conversation context with the coordinator.

### Use Case

- Help desk with billing, support, and sales specialists
- Code assistant that routes to reviewer, documenter, or debugger
- Multi-domain expert system

### Syntax

```streetrace
agent coordinator:
    instruction coordinator_prompt
    delegate specialist1, specialist2, specialist3
```

### Example

```streetrace
model main = anthropic/claude-sonnet

# Specialized agents
prompt code_expert_prompt: """You are a code analysis expert.
Analyze code for quality issues, security vulnerabilities,
and provide actionable recommendations."""

agent code_expert:
    tools fs
    instruction code_expert_prompt
    description "Expert at analyzing and explaining code"

prompt research_expert_prompt: """You are a research expert.
Search the web for relevant information and synthesize
findings into clear, actionable insights."""

agent research_expert:
    tools web
    instruction research_expert_prompt
    description "Expert at web research and information synthesis"

# Coordinator that routes to specialists
prompt coordinator_prompt: """You are a project coordinator.
Understand the user's request and delegate to the appropriate
specialist:
- For code analysis tasks, delegate to code_expert
- For research tasks, delegate to research_expert

Synthesize results from specialists into a coherent response."""

agent:
    tools fs
    instruction coordinator_prompt
    delegate code_expert, research_expert
    description "Coordinates tasks across specialists"
```

### How It Works

1. User sends a request to the coordinator
2. Coordinator's LLM analyzes the request
3. LLM decides which specialist should handle it
4. Request is delegated to the chosen specialist
5. Specialist processes the request and responds

The coordinator can synthesize results if needed, or fully hand off the conversation.

## Hierarchical Pattern (use)

The hierarchical pattern lets an agent call other agents as tools. The parent agent
controls when and how to invoke child agents.

At runtime, agents listed in `use` are wrapped as ADK AgentTools and added to the
parent agent's tools. The parent explicitly invokes them as tools, each call runs
in isolation, and results flow back to the parent for aggregation.

### Use Case

- Complex tasks requiring multiple capabilities
- Workflows that aggregate results from multiple agents
- Agents that need to orchestrate other agents

### Syntax

```streetrace
agent parent:
    instruction parent_prompt
    use child1, child2
```

### Example

```streetrace
model main = anthropic/claude-sonnet

# Helper agents (tools)
prompt extractor_prompt: """You are a code extraction specialist.
When given a file path and description, locate and extract
the relevant code snippet. Return the extracted code with
line numbers and context."""

agent extractor:
    tools fs
    instruction extractor_prompt
    description "Extracts code snippets from files"

prompt analyzer_prompt: """You are a code analyzer.
Analyze the provided code snippet for:
- Security vulnerabilities
- Performance issues
- Code quality problems
Return a structured analysis."""

agent analyzer:
    instruction analyzer_prompt
    description "Analyzes code for issues"

prompt documenter_prompt: """You are a documentation writer.
Given code and its analysis, generate clear documentation
including:
- Purpose and usage
- Parameters and return values
- Examples"""

agent documenter:
    instruction documenter_prompt
    description "Generates documentation from code"

# Parent agent that orchestrates helpers as tools
prompt orchestrator_prompt: """You are a code documentation assistant.
Help users document their codebase by:
1. Use the extractor to get code from files
2. Use the analyzer to understand the code
3. Use the documenter to generate documentation

Each helper is available as a tool you can call."""

agent:
    tools fs
    instruction orchestrator_prompt
    use extractor, analyzer, documenter
    description "Orchestrates code documentation workflow"
```

### How It Works

1. User sends a request to the parent agent
2. Parent agent's LLM decides to use a helper agent
3. Parent explicitly invokes the helper as a tool
4. Helper executes and returns results to parent
5. Parent aggregates and processes results
6. Parent responds to user

Results always flow back to the parent agent.

## delegate vs use

Understanding when to use `delegate` versus `use` is important:

| Aspect | delegate | use |
|--------|----------|-----|
| Control | LLM decides transfer | Explicit invocation |
| Return | May not return | Always returns |
| Context | Shared conversation | Isolated execution |
| Pattern | Routing/handoff | Task delegation |

### Choose delegate When

- You want the LLM to decide routing
- The specialist may fully take over
- Multiple specialists for different domains

### Choose use When

- You need explicit control over invocation
- Results must be aggregated
- Parent orchestrates the workflow

### Agent Descriptions

When using `delegate` or `use`, always provide a `description` for your agents. The
description helps the LLM understand what each agent does and when to use it.

```streetrace
agent code_reviewer:
    tools fs
    instruction code_review_prompt
    description "Reviews code for quality, security, and style issues"

agent doc_writer:
    tools fs
    instruction doc_writer_prompt
    description "Writes documentation for code and APIs"

agent:
    instruction coordinator_prompt
    delegate code_reviewer, doc_writer
    description "Routes tasks to the appropriate specialist"
```

Good descriptions are:
- Concise but informative (one sentence)
- Action-oriented (describes what the agent does)
- Specific about the agent's expertise

## Iterative Pattern (loop)

The loop pattern repeats a workflow until a condition is met or maximum iterations
are reached. Use this for quality improvement workflows.

### Use Case

- Code improvement through review cycles
- Document refinement
- Multi-step analysis with feedback

### Syntax

```streetrace
# Bounded loop (recommended)
loop max 5 do
    # statements
end

# Unbounded loop (use with exit condition)
loop do
    # statements
    if $done:
        return $result
end
```

### Example

```streetrace
model main = anthropic/claude-sonnet

schema CodeQuality:
    score: int
    issues: list[string]
    passed: bool

schema RefineResult:
    improved_code: string
    changes_made: list[string]

prompt quality_check expecting CodeQuality: """Analyze the code quality.
Return a score from 0-100, list any issues found, and set passed=true
if score is 80 or above."""

prompt refine_code expecting RefineResult: """Improve the code based on
the issues found. Apply fixes for each issue and return the improved code
along with a list of changes made."""

prompt main_instruction: """You are a code quality improvement assistant.
Help users improve their code through iterative refinement."""

flow refine_with_limit $code:
    $current_code = $code

    # Loop with max 5 iterations to prevent infinite loops
    loop max 5 do
        $quality = call llm quality_check $current_code
        $result = call llm refine_code $current_code
        $current_code = $result.improved_code
        log "Refinement iteration completed"
    end

    return { success: true, code: $current_code }

agent:
    tools fs
    instruction main_instruction
    description "Iteratively improves code quality"
```

### How It Works

1. Loop executes the body statements
2. Each iteration can check conditions
3. Use `return` to exit early when done
4. Loop terminates when max iterations reached
5. Final result is returned

### Best Practices

- Always use `loop max N` for bounded iteration
- Include exit conditions for quality thresholds
- Log iteration progress for debugging
- Return meaningful results on completion

## How Patterns Work at Runtime

Understanding how these patterns execute helps you design effective multi-agent systems.

### Agent Hierarchy Creation

When you run a DSL agent file, the loader:

1. Compiles the `.sr` file to Python bytecode
2. Creates the root agent from the default (unnamed) agent definition
3. For each agent in `delegate`, creates a sub-agent recursively
4. For each agent in `use`, creates an AgentTool wrapper recursively
5. Nested patterns are fully supported (sub-agents can have their own sub-agents/tools)

### Execution Flow

```
User Request
    |
    v
Root Agent (coordinator)
    |
    +--[delegate]--> Sub-Agent A (shares context)
    |                    |
    |                    +--[use]--> Helper 1 (isolated call)
    |                    +--[use]--> Helper 2 (isolated call)
    |
    +--[delegate]--> Sub-Agent B (shares context)
```

### Resource Management

All agents and their nested sub-agents/tools are properly cleaned up when the session
ends. Cleanup follows depth-first order, closing child agents before parents.

## Combined Patterns

Real-world applications often combine patterns. Here is an example combining all three:

```streetrace
model main = anthropic/claude-sonnet

# Helper agents (leaf level)
prompt formatter_prompt: """Format code according to style guidelines."""
agent formatter:
    instruction formatter_prompt
    description "Formats code to style standards"

prompt linter_prompt: """Check code for common errors and style issues."""
agent linter:
    instruction linter_prompt
    description "Lints code for issues"

# Specialist agent using helpers
prompt code_reviewer_prompt: """You are a code reviewer.
Use the formatter and linter tools to thoroughly review code.
Synthesize findings into a review."""

agent code_reviewer:
    tools fs
    instruction code_reviewer_prompt
    use formatter, linter
    description "Comprehensive code reviewer"

prompt doc_writer_prompt: """Write documentation for code."""
agent doc_writer:
    tools fs
    instruction doc_writer_prompt
    description "Documentation specialist"

# Coordinator routing to specialists
prompt coordinator_prompt: """You are a development team coordinator.
Delegate tasks to the appropriate specialist:
- Code review tasks go to code_reviewer
- Documentation tasks go to doc_writer"""

agent:
    tools fs
    instruction coordinator_prompt
    delegate code_reviewer, doc_writer
    description "Development team coordinator"
```

This example combines:
- **Hierarchical**: `code_reviewer` uses `formatter` and `linter`
- **Coordinator**: Main agent delegates to `code_reviewer` or `doc_writer`

## Validation and Errors

The DSL validates multi-agent patterns at compile time:

### Undefined Agent Reference

```
error[E0001]: undefined reference to agent 'nonexistent'
  --> my_agent.sr:15:14
   |
15 |     delegate nonexistent
   |              ^^^^^^^^^^^
```

**Fix**: Ensure all referenced agents are defined before use.

### Circular Reference

```
error[E0011]: circular agent reference detected: agent_a -> agent_b -> agent_a
  --> my_agent.sr:8:9
```

**Fix**: Reorganize agent relationships to avoid cycles.

### Both delegate and use Warning

```
warning[W0002]: agent 'my_agent' has both delegate and use - this is unusual
  --> my_agent.sr:10:1
```

**Fix**: Consider whether you need both patterns, or reorganize into separate agents.

## Example Files

The repository includes complete examples:

| File | Description |
|------|-------------|
| `agents/examples/dsl/coordinator.sr` | Help desk coordinator pattern |
| `agents/examples/dsl/hierarchical.sr` | Code documentation with helpers |
| `agents/examples/dsl/iterative.sr` | Quality improvement loop |
| `agents/examples/dsl/combined.sr` | All patterns combined |

Validate examples with:

```bash
poetry run streetrace check agents/examples/dsl/coordinator.sr
poetry run streetrace check agents/examples/dsl/hierarchical.sr
poetry run streetrace check agents/examples/dsl/iterative.sr
poetry run streetrace check agents/examples/dsl/combined.sr
```

## See Also

- [Syntax Reference](syntax-reference.md) - Complete syntax documentation
- [Getting Started](getting-started.md) - Introduction to Streetrace DSL
- [Troubleshooting](troubleshooting.md) - Common errors and solutions
