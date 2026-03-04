# DSL Agentic Patterns

| Field | Value |
|-------|-------|
| **Parent RFC** | [RFC-017: Streetrace Agent Definition DSL](../../../rfc/017-streetrace-dsl.md) |
| **Status** | Draft |
| **Created** | 2026-01-21 |
| **Authors** | Streetrace Engineering |

## Overview

This document describes how to implement common multi-agent patterns from Google ADK using the Streetrace DSL. It covers all patterns documented in the [ADK Multi-Agent documentation](https://google.github.io/adk-docs/agents/multi-agents/).

---

## 1. Pattern Summary

| Pattern | ADK Mechanism | Current DSL Support | Required DSL Addition |
|---------|--------------|---------------------|----------------------|
| Sequential Pipeline | `SequentialAgent` | Yes (implicit) | None |
| Parallel Fan-Out/Gather | `ParallelAgent` | Yes (`parallel do/end`) | None |
| Coordinator/Dispatcher | `sub_agents` | No | `delegate` keyword |
| Hierarchical Task Decomposition | `AgentTool` | No | `use` keyword |
| Review/Critique (Generator-Critic) | `SequentialAgent` | Yes (implicit) | None |
| Iterative Refinement | `LoopAgent` | No | `loop` block |
| Human-in-the-Loop | Callbacks + Policy | Partial (`escalate`) | Callback hooks |

---

## 2. Sequential Pipeline Pattern

### Description

Agents execute in fixed order where each step's output becomes the next step's input. Uses `SequentialAgent` with shared session state for communication.

### Current DSL Support

**Full support** - Sequential execution is the default behavior when agents are called in sequence within a flow.

### DSL Example

```streetrace
model main = anthropic/claude-sonnet

prompt validator_instruction:
    Validate the input data format and structure.
    Report any issues found.

prompt processor_instruction:
    Process the validated data.
    Transform it according to business rules.

prompt reporter_instruction:
    Generate a final report from the processed data.
    Summarize key findings.

agent validator:
    instruction validator_instruction
    description "Validates input data"

agent processor:
    instruction processor_instruction
    description "Processes validated data"

agent reporter:
    instruction reporter_instruction
    description "Generates final reports"

flow sequential_pipeline $input:
    # Each agent runs after the previous one completes
    # Output from one becomes input to the next
    $validated = run agent validator $input
    $processed = run agent processor $validated
    $report = run agent reporter $processed
    return $report

on start do
    $input_prompt = initial user prompt
    $result = run sequential_pipeline $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent, SequentialAgent

validator = LlmAgent(name="validator", instruction="Validate the input...")
processor = LlmAgent(name="processor", instruction="Process the validated...")
reporter = LlmAgent(name="reporter", instruction="Generate a final report...")

# The DSL compiler detects sequential flow and generates:
pipeline = SequentialAgent(
    name="sequential_pipeline",
    sub_agents=[validator, processor, reporter]
)
```

---

## 3. Parallel Fan-Out/Gather Pattern

### Description

Multiple independent tasks run concurrently, then results are combined for synthesis. Uses `ParallelAgent` for concurrent execution, often nested in `SequentialAgent` for the gather phase.

### Current DSL Support

**Full support** via `parallel do/end` block.

### DSL Example

```streetrace
model main = anthropic/claude-sonnet

prompt web_search_instruction:
    Search the web for information on the given topic.
    Return relevant facts and sources.

prompt doc_search_instruction:
    Search internal documentation for relevant information.
    Return matching content with references.

prompt synthesize_instruction:
    Combine research results from multiple sources.
    Provide a comprehensive summary with citations.

agent web_searcher:
    instruction web_search_instruction
    description "Searches web for information"

agent doc_searcher:
    instruction doc_search_instruction
    description "Searches internal docs"

agent synthesizer:
    instruction synthesize_instruction
    description "Synthesizes research results"

flow research $topic:
    # Fan-out: Run both searches in parallel
    parallel do
        $web_results = run agent web_searcher $topic
        $doc_results = run agent doc_searcher $topic
    end

    # Gather: Synthesize results
    $combined = run agent synthesizer $web_results $doc_results
    return $combined

on start do
    $input_prompt = initial user prompt
    $result = run research $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

web_searcher = LlmAgent(name="web_searcher", instruction="Search the web...")
doc_searcher = LlmAgent(name="doc_searcher", instruction="Search internal...")
synthesizer = LlmAgent(name="synthesizer", instruction="Combine research...")

# Parallel fan-out
fan_out = ParallelAgent(
    name="research_fan_out",
    sub_agents=[web_searcher, doc_searcher]
)

# Sequential with gather phase
research_flow = SequentialAgent(
    name="research",
    sub_agents=[fan_out, synthesizer]
)
```

---

## 4. Coordinator/Dispatcher Pattern (NEW)

### Description

A central LLM agent manages and routes tasks to specialized sub-agents based on request type. Uses LLM-driven delegation via `sub_agents` in ADK.

### Current DSL Support

**Not supported** - Requires new `delegate` keyword.

### Proposed DSL Syntax

```streetrace
# Coordinator/Dispatcher Pattern
# User asks "My payment failed" -> ADK routes to billing_agent
# User asks "I can't log in" -> ADK routes to support_agent

model main = anthropic/claude-sonnet

prompt billing_instruction:
    You are a billing specialist.
    Handle payment issues, invoice questions, and subscription management.
    Be helpful and thorough in resolving billing concerns.

agent billing_agent:
    instruction billing_instruction
    description "Handles billing and payment inquiries"

prompt support_instruction:
    You are a technical support specialist.
    Help users resolve technical issues, errors, and account access problems.
    Guide users through troubleshooting steps.

agent support_agent:
    instruction support_instruction
    description "Handles technical support requests"

prompt sales_instruction:
    You are a sales representative.
    Answer questions about pricing, plans, and upgrades.
    Help customers find the right solution for their needs.

agent sales_agent:
    instruction sales_instruction
    description "Handles sales and pricing inquiries"

prompt coordinator_instruction:
    You are the main help desk coordinator.
    Route user requests to the appropriate specialist:
    - Billing agent: payment issues, invoices, subscriptions
    - Support agent: technical problems, errors, login issues
    - Sales agent: pricing, plans, upgrades

    Analyze the user's request and transfer to the most appropriate agent.

agent coordinator:
    instruction coordinator_instruction
    description "Main help desk router"
    # NEW SYNTAX: delegate lists agents this agent can transfer to
    delegate billing_agent, support_agent, sales_agent

on start do
    $input_prompt = initial user prompt
    # Coordinator uses LLM to decide which sub-agent to invoke
    $result = run agent coordinator $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent

billing_agent = LlmAgent(
    name="billing_agent",
    instruction="You are a billing specialist..."
)

support_agent = LlmAgent(
    name="support_agent",
    instruction="You are a technical support specialist..."
)

sales_agent = LlmAgent(
    name="sales_agent",
    instruction="You are a sales representative..."
)

# Coordinator with sub_agents for LLM-driven delegation
coordinator = LlmAgent(
    name="coordinator",
    instruction="You are the main help desk coordinator...",
    description="Main help desk router",
    sub_agents=[billing_agent, support_agent, sales_agent]
)
```

### Grammar Addition

```lark
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate  # NEW
```

---

## 5. Hierarchical Task Decomposition Pattern (NEW)

### Description

Multi-level agent tree where higher levels delegate complex problems to specialized lower levels. Uses `AgentTool` to wrap agents as callable tools.

### Current DSL Support

**Not supported** - Requires new `use` keyword.

### Proposed DSL Syntax

```streetrace
# Hierarchical Task Decomposition Pattern
# High-level agent calls mid-level agent as a tool
# Mid-level agent calls low-level agents as tools
# Results flow back up the hierarchy

model main = anthropic/claude-sonnet

prompt web_searcher_instruction:
    Perform web searches for factual information.
    Return relevant findings with source URLs.

agent web_searcher:
    instruction web_searcher_instruction
    description "Performs web searches for facts"

prompt summarizer_instruction:
    Summarize provided text concisely.
    Preserve key points and important details.

agent summarizer:
    instruction summarizer_instruction
    description "Summarizes text content"

prompt research_assistant_instruction:
    Find and summarize information on a given topic.
    Use web search to gather facts, then summarize findings.

agent research_assistant:
    instruction research_assistant_instruction
    description "Finds and summarizes information"
    # NEW SYNTAX: use wraps agents as tools (AgentTool)
    use web_searcher, summarizer

prompt report_writer_instruction:
    Write a comprehensive report on the requested topic.
    Use the research assistant to gather background information.
    Structure the report with introduction, findings, and conclusions.

agent report_writer:
    instruction report_writer_instruction
    description "Writes detailed reports on topics"
    # report_writer calls research_assistant as a tool
    use research_assistant

on start do
    $input_prompt = initial user prompt
    # User interacts with report_writer
    # report_writer calls research_assistant tool
    # research_assistant calls web_searcher and summarizer tools
    # Results flow back up
    $report = run agent report_writer $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

# Low-level agents
web_searcher = LlmAgent(
    name="web_searcher",
    description="Performs web searches for facts."
)

summarizer = LlmAgent(
    name="summarizer",
    description="Summarizes text content."
)

# Mid-level agent with low-level agents as tools
research_assistant = LlmAgent(
    name="research_assistant",
    instruction="Find and summarize information on a topic.",
    description="Finds and summarizes information.",
    tools=[
        agent_tool.AgentTool(agent=web_searcher),
        agent_tool.AgentTool(agent=summarizer)
    ]
)

# High-level agent with mid-level agent as tool
report_writer = LlmAgent(
    name="report_writer",
    instruction="Write a comprehensive report on the requested topic...",
    description="Writes detailed reports on topics.",
    tools=[agent_tool.AgentTool(agent=research_assistant)]
)
```

### Grammar Addition

```lark
agent_property: "tools" name_list _NL                 -> agent_tools
              | "instruction" NAME _NL                -> agent_instruction
              | "retry" NAME _NL                      -> agent_retry
              | "timeout" timeout_value _NL           -> agent_timeout
              | "description" STRING _NL              -> agent_description
              | "delegate" name_list _NL              -> agent_delegate
              | "use" name_list _NL                   -> agent_use  # NEW
```

---

## 6. Review/Critique Pattern (Generator-Critic)

### Description

Dedicated agents validate or improve generated output through systematic review. Sequential arrangement where generator saves output, then reviewer evaluates it.

### Current DSL Support

**Full support** - Implemented using sequential flow with multiple agents.

### DSL Example

```streetrace
model main = anthropic/claude-sonnet

prompt draft_writer_instruction:
    Write a draft response based on the given prompt.
    Focus on accuracy, clarity, and completeness.

prompt fact_checker_instruction:
    Review the draft for factual accuracy.
    Flag any unsupported claims or potential errors.
    Provide a review status and list of issues.

prompt editor_instruction:
    Review the draft for clarity, grammar, and style.
    Suggest improvements and polish the final output.

agent draft_writer:
    instruction draft_writer_instruction
    description "Writes initial drafts"

agent fact_checker:
    instruction fact_checker_instruction
    description "Verifies factual accuracy"

agent editor:
    instruction editor_instruction
    description "Improves clarity and style"

schema ReviewResult:
    approved: bool
    issues: list[string]
    improved_text: string

flow review_pipeline $prompt:
    # Generate draft
    $draft = run agent draft_writer $prompt

    # Review for facts
    $fact_review = run agent fact_checker $draft

    # Edit for style
    $final = run agent editor $draft $fact_review

    return $final

on start do
    $input_prompt = initial user prompt
    $result = run review_pipeline $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent, SequentialAgent

draft_writer = LlmAgent(name="draft_writer", instruction="Write a draft...")
fact_checker = LlmAgent(name="fact_checker", instruction="Review the draft...")
editor = LlmAgent(name="editor", instruction="Review for clarity...")

# Sequential review pipeline
review_pipeline = SequentialAgent(
    name="review_pipeline",
    sub_agents=[draft_writer, fact_checker, editor]
)
```

---

## 7. Iterative Refinement Pattern (NEW)

### Description

Agents repeatedly improve outputs through cycles until satisfactory results emerge or iteration limits are reached. Uses `LoopAgent` for repeated execution with exit conditions.

### Current DSL Support

**Not supported** - Requires new `loop` block construct.

### Proposed DSL Syntax

```streetrace
# Iterative Refinement Pattern
# Agent repeatedly improves output until quality threshold met
# or maximum iterations reached

model main = anthropic/claude-sonnet

schema QualityCheck:
    score: float
    feedback: string
    done: bool

prompt improver_instruction:
    Improve the provided text based on the feedback.
    Focus on addressing the specific issues mentioned.

prompt quality_checker_instruction expecting QualityCheck:
    Evaluate the quality of the text.
    Score from 0.0 to 1.0 (1.0 is perfect).
    Provide specific feedback for improvement.
    Set done=true if score >= 0.9 or no more improvements possible.

agent improver:
    instruction improver_instruction
    description "Improves text based on feedback"

agent quality_checker:
    instruction quality_checker_instruction
    description "Evaluates text quality"

flow iterative_refinement $initial_text:
    $current_text = $initial_text

    # NEW SYNTAX: loop with max iterations
    loop max 5 do
        # Check quality
        $quality = run agent quality_checker $current_text

        # Exit if quality is good enough
        if $quality.done:
            return $current_text

        # Otherwise improve and continue
        $current_text = run agent improver $current_text $quality.feedback
    end

    # Return best effort after max iterations
    return $current_text

on start do
    $input_prompt = initial user prompt
    $result = run iterative_refinement $input_prompt
end
```

### Compiled Python (Conceptual)

```python
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent

improver = LlmAgent(name="improver", instruction="Improve the provided text...")
quality_checker = LlmAgent(name="quality_checker", instruction="Evaluate quality...")

# Refinement iteration (runs in a loop)
refinement_step = SequentialAgent(
    name="refinement_step",
    sub_agents=[quality_checker, improver]
)

# Loop agent with max iterations
# Exit condition based on quality_checker setting escalate flag
iterative_refinement = LoopAgent(
    name="iterative_refinement",
    sub_agents=[refinement_step],
    max_iterations=5
)
```

### Grammar Addition

```lark
// Add to flow_statement or handler_statement
loop_block: "loop" "max" INT "do" _NL _INDENT flow_body _DEDENT "end" _NL?
          | "loop" "do" _NL _INDENT flow_body _DEDENT "end" _NL?  # infinite loop with break
```

---

## 8. Human-in-the-Loop Pattern

### Description

Workflow pauses for human review/approval at decision points before proceeding. Integrates human decision-making into agent workflows.

### Current DSL Support

**Partial** - `escalate to human` exists for explicit escalation, but automated approval workflows require callback hooks.

### DSL Example (Current Capability)

```streetrace
# Current: Explicit escalation
model main = anthropic/claude-sonnet

schema ActionPlan:
    action: string
    risk_level: string
    requires_approval: bool

prompt planner_instruction expecting ActionPlan:
    Create an action plan for the request.
    Flag high-risk actions that require human approval.

agent planner:
    instruction planner_instruction
    description "Creates action plans"

flow approval_workflow $request:
    $plan = run agent planner $request

    # Escalate high-risk actions to human
    if $plan.requires_approval:
        escalate to human "Approval required for high-risk action"

    return $plan

on start do
    $input_prompt = initial user prompt
    $result = run approval_workflow $input_prompt
end
```

### Proposed Enhancement

For full Human-in-the-Loop support with callbacks, we would need a policy-based approach:

```streetrace
# FUTURE: Policy-based human approval
policy human_approval:
    trigger: risk_level == "high"
    action: pause_for_approval
    timeout: 24 hours
    on_timeout: abort
```

This is documented as a future enhancement (Phase 2).

---

## 9. Semantic Differences: `delegate` vs `use`

Understanding the difference between `delegate` and `use` is crucial for choosing the right pattern:

| Aspect | `delegate` (sub_agents) | `use` (AgentTool) |
|--------|------------------------|-------------------|
| Control Transfer | LLM decides when to transfer | Explicit tool call by LLM |
| Return Behavior | May not return to caller | Always returns to caller |
| Conversation Context | Shared conversation | Isolated execution |
| Use Case | Routing, handoff | Task delegation |
| ADK Mechanism | `sub_agents=[...]` | `tools=[AgentTool(...)]` |

### When to Use `delegate`

- **Routing scenarios**: User requests need to go to specialized handlers
- **Full handoff**: The sub-agent takes over the conversation
- **Multiple specialists**: Central coordinator routes to the right expert

```streetrace
# User talks to coordinator, gets transferred to billing
agent coordinator:
    instruction coordinator_instruction
    delegate billing, support, sales  # LLM chooses when to transfer
```

### When to Use `use`

- **Tool-like behavior**: Agent needs capabilities from other agents
- **Hierarchical work**: Higher-level agent orchestrates lower-level ones
- **Results aggregation**: Caller combines results from multiple agent-tools

```streetrace
# Report writer uses research assistant as a tool
agent report_writer:
    instruction report_writer_instruction
    use research_assistant  # Explicit tool invocation
```

---

## 10. Combined Patterns Example

Real-world applications often combine multiple patterns:

```streetrace
model main = anthropic/claude-sonnet
model fast = anthropic/haiku

# === LOW-LEVEL AGENTS ===

prompt data_fetcher_instruction:
    Fetch data from the specified source.

agent data_fetcher:
    instruction data_fetcher_instruction
    description "Fetches data from sources"

prompt data_validator_instruction:
    Validate data structure and content.

agent data_validator:
    instruction data_validator_instruction
    description "Validates data quality"

# === MID-LEVEL AGENT (Hierarchical) ===

prompt data_processor_instruction:
    Process data by fetching and validating it.
    Use available tools to complete the task.

agent data_processor:
    instruction data_processor_instruction
    description "Processes data end-to-end"
    use data_fetcher, data_validator

# === SPECIALIZED AGENTS FOR ROUTING ===

prompt report_agent_instruction:
    Generate reports from processed data.

agent report_agent:
    instruction report_agent_instruction
    description "Generates data reports"
    use data_processor

prompt analysis_agent_instruction:
    Perform analysis on processed data.

agent analysis_agent:
    instruction analysis_agent_instruction
    description "Analyzes data patterns"
    use data_processor

# === COORDINATOR (Dispatcher Pattern) ===

prompt coordinator_instruction:
    Route requests to appropriate specialist:
    - Report agent: Generate reports, summaries, exports
    - Analysis agent: Analyze trends, patterns, anomalies

    Analyze the request and delegate accordingly.

agent coordinator:
    instruction coordinator_instruction
    description "Routes data requests"
    delegate report_agent, analysis_agent

on start do
    $input_prompt = initial user prompt
    $result = run agent coordinator $input_prompt
end
```

This example combines:
- **Hierarchical**: `data_processor` uses `data_fetcher` and `data_validator`
- **Dispatcher**: `coordinator` delegates to `report_agent` or `analysis_agent`
- **Sequential**: Within each agent's execution

---

## 11. Implementation Requirements

### Grammar Additions

1. **`delegate` keyword** for agent property (Coordinator pattern)
2. **`use` keyword** for agent property (Hierarchical pattern)
3. **`loop` block** for flow statements (Iterative Refinement pattern)

### AST Node Changes

```python
@dataclass
class AgentDef:
    name: str | None
    tools: list[str]
    instruction: str
    retry: str | None = None
    timeout_ref: str | None = None
    timeout_value: int | None = None
    timeout_unit: str | None = None
    description: str | None = None
    delegate: list[str] | None = None  # NEW: sub_agents
    use: list[str] | None = None       # NEW: AgentTool
    meta: SourcePosition | None = None

@dataclass
class LoopBlock:
    """Loop block for iterative refinement."""
    max_iterations: int | None
    body: list[AstNode]
    meta: SourcePosition | None = None
```

### Semantic Analysis

- Validate `delegate` and `use` reference existing agents
- Detect circular delegation/use references
- Warn if agent uses both `delegate` and `use` (unusual pattern)

### Code Generation

- Generate `sub_agents=[...]` for `delegate`
- Generate `tools=[AgentTool(...)]` for `use`
- Generate `LoopAgent` wrapper for `loop` blocks

---

## References

- [ADK Multi-Agent Documentation](https://google.github.io/adk-docs/agents/multi-agents/)
- [RFC-017: Streetrace Agent Definition DSL](../../../rfc/017-streetrace-dsl.md)
- [017-dsl-grammar.md](../../../../home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-grammar.md)
- [017-dsl-examples.md](../../../../home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-examples.md)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-21 | 0.1 | Initial agentic patterns documentation |
