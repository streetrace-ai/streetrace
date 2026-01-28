# Design: Streetrace Code Review Agent

## Overview

This document describes the design of a comprehensive GitHub PR code review agent using the Streetrace DSL. The goal is to create an award-winning code reviewer that achieves top benchmark performance (>55% F-score, <10% false positive rate) through a multi-agent architecture.

### Design Principles

1. **Map/Reduce Pattern**: Chunk inputs and run parallel read-only reviewers
2. **Confidence-Based Filtering**: Score all findings and filter low-confidence noise
3. **Multi-Agent Specialization**: Dedicated agents for security, correctness, style, etc.
4. **Context-First**: Explicit, systematic context retrieval at every level
5. **Calibrated Scoring**: Consistent scoring rubric across all reviewers

### Key Insight: Systematic Context Retrieval

Context is the #1 differentiator in code review quality. We cannot leave context gathering to chance - it must be explicit and systematic at every level:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CONTEXT HIERARCHY                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Level 1: Repository Context (built once, PR-aware)                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ • README, CONTRIBUTING, style guides                                  │ │
│  │ • Language/framework conventions                                      │ │
│  │ • Architecture docs relevant to PR's affected areas                   │ │
│  │ • Built WITH PR description in mind (knows review categories)         │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Level 2: PR Context (built once)                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ • PR description, title, author                                       │ │
│  │ • Linked issues (parsed from description, closes/fixes)               │ │
│  │ • Linked PRs (mentioned in description)                               │ │
│  │ • Review status, CI status                                            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Level 3: Chunk Context (built per chunk - CRITICAL)                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ • Git blame for affected lines → commit SHAs                          │ │
│  │ • Commit messages for those SHAs                                      │ │
│  │ • Issues/bugs linked from commit messages                             │ │
│  │ • Other PRs that touched these same lines recently                    │ │
│  │ • Summarized WITH review categories in mind                           │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Each reviewer receives: Repo Context + PR Context + Chunk Context          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

This layered approach ensures:
- Large PRs don't overwhelm context windows (context is chunked)
- Historical context is always available (blame, related issues)
- Context is purpose-driven (built with review categories in mind)

---

## Architecture Options

We propose three architectural variants to compare in benchmarks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ARCHITECTURE COMPARISON                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  V1: Monolithic           V2: Parallel Flow          V3: Tool-Use (use)    │
│  ┌───────────────┐        ┌─────────────────────┐      ┌───────────────┐   │
│  │               │        │    Orchestrator     │      │  Orchestrator │   │
│  │   Single      │        │   (explicit flow)   │      │   (LLM-driven)│   │
│  │   Reviewer    │        └──────────┬──────────┘      └───────┬───────┘   │
│  │               │           parallel do                 use as│tools      │
│  └───────┬───────┘        ┌──────────┼──────────┐      ┌───────┼───────┐   │
│          │                ▼          ▼          ▼      ▼       ▼       ▼   │
│          ▼           ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  ┌───────────────┐   │Security│ │  Bug   │ │ Style  │ │Security│ │  Bug   ││
│  │    Filter     │   └───┬────┘ └───┬────┘ └───┬────┘ │  Tool  │ │  Tool  ││
│  └───────────────┘       │          │          │      └───┬────┘ └───┬────┘│
│                          └──────────┼──────────┘          │          │     │
│                                     ▼                     └────┬─────┘     │
│                             ┌───────────────┐                  ▼           │
│                             │  Validator &  │          ┌───────────────┐   │
│                             │   Deduplicator│          │   Validator   │   │
│                             └───────────────┘          │     Tool      │   │
│                                                        └───────────────┘   │
│  Simple, fast              Best precision/recall       LLM orchestration   │
│  Limited accuracy          Explicit control            Simpler DSL         │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pattern Clarification**:
- `delegate`: Routing pattern - parent hands off entire task to a sub-agent
- `use`: Tool-use pattern - parent calls sub-agents as tools, combines results

---

## Agent Definitions

### Version 1: Monolithic Single-Pass Reviewer

**Full implementation**: `agents/code-review/v1-monolithic.sr`

The simplest approach - one agent reviews everything with structured output. Despite being "monolithic", it still includes:
- PR-aware context building
- Historical context (blame, linked issues)
- Confidence-based filtering

```
flow main:
    # 1. Fetch PR info and diff first
    parallel do
        $pr_info = run agent pr_fetcher $input
        $diff = run agent diff_fetcher $input
    end

    # 2. Build PR-aware context (needs PR info to prioritize relevant context)
    $context = run agent context_gatherer $pr_info

    # 3. Combine all context
    $full_context = { pr: $pr_info, repo_and_history: $context }

    # 4. Single-pass review with full context
    $review = call llm reviewer_instruction $full_context $diff

    # 5. Post-filter low-confidence findings
    $review.findings = filter($review.findings, $f -> $f.confidence >= 80)

    return $review
```

**Agents**:
- `pr_fetcher` - Fetches PR metadata
- `context_gatherer` - Builds comprehensive context (repo + history)
- `diff_fetcher` - Fetches PR diff

**Trade-offs**:
- ✅ Simple, fast, single LLM call for review
- ✅ Still has PR-aware context and historical context
- ❌ No specialization or redundancy
- ❌ Limited accuracy compared to multi-agent
- ❌ Context window limits for large PRs

---

### Version 2: Parallel Multi-Agent with Validation

**Full implementation**: `agents/code-review/v2-parallel.sr`

The recommended approach - specialized reviewers with per-chunk context and validation.

**Key Pattern: Per-Chunk Context Building**

```
flow main:
    # Phase 1A: Fetch PR info and diff first
    parallel do
        $pr_info = run agent pr_fetcher $input
        $diff = run agent diff_fetcher $input
    end

    # Phase 1B: Build PR-aware repo context (needs PR info)
    $repo_context = run agent context_builder $pr_info

    # Phase 2: Chunk the diff
    $chunks = call llm chunk_splitter $diff

    # Phase 3: For each chunk, build context + review
    $all_findings = []
    for $chunk in $chunks do
        # Build chunk-specific historical context (blame, commits, linked issues)
        $chunk_context = run agent chunk_context_builder $chunk $pr_info

        # Combine all context levels
        $full_context = {
            repo: $repo_context,
            pr: $pr_info,
            chunk_history: $chunk_context
        }

        # Run all specialists in parallel per chunk
        parallel do
            $security_findings = call llm security_reviewer $full_context $chunk
            $bug_findings = call llm bug_reviewer $full_context $chunk
            $style_findings = call llm style_reviewer $full_context $chunk
        end

        # Collect findings
        $all_findings = concat($all_findings, $security_findings.findings)
        $all_findings = concat($all_findings, $bug_findings.findings)
        $all_findings = concat($all_findings, $style_findings.findings)
    end

    # Phase 4-7: Validate, deduplicate, patch, compile
    $validated = run validate_all $all_findings $full_context
    $unique = call llm deduplicator $validated
    $patches = run generate_all_patches $unique $diff
    $final = call llm final_compiler $pr_info $unique $patches

    return $final
```

**The chunk_context_builder agent** (critical for quality):
```
prompt chunk_context_instruction: """Build context for this specific code chunk.

Steps:
1. Identify the file(s) and line ranges in this chunk
2. Run git blame on the affected lines to get commit SHAs
3. Fetch commit messages for those SHAs
4. Parse commit messages for linked issues (Fixes #123, Closes #456, etc.)
5. If issues are found, fetch their descriptions
6. Check for other recent PRs that touched these same files

Return a SUMMARY that includes:
- Why these lines exist (based on blame/commit messages)
- What bugs or issues led to the current implementation
- Any related PRs that touched this code recently
- Key context a reviewer should know about this code's history"""

agent chunk_context_builder:
    tools github, fs
    instruction chunk_context_instruction
    description "Builds historical context for a code chunk"
```

**Agents**:
- `pr_fetcher` - Fetches PR metadata
- `context_builder` - Builds PR-aware repository context
- `diff_fetcher` - Fetches PR diff
- `chunk_context_builder` - Builds per-chunk historical context (blame, issues)
- `security_reviewer`, `bug_reviewer`, `style_reviewer` - Specialized reviewers
- `validator` - Validates findings against code

---

### Version 3: Hierarchical Tool-Use Pattern

**Full implementation**: `agents/code-review/v3-hierarchical.sr`

Uses ADK's `use` keyword to expose specialist agents as tools for the orchestrator.

**Key Distinction**:
- `delegate` = routing (sub-agent takes over entire task)
- `use` = tool-use (parent orchestrates, calling sub-agents for subtasks)

For code review, we need the orchestrator to **call specialists as tools** and **combine their outputs** - that's the `use` pattern.

**Orchestrator with context builders and specialists as tools:**
```
agent:
    tools github, fs
    instruction orchestrator_instruction
    use context_builder, chunk_context_builder, security_specialist, bug_specialist, quality_specialist, validator, synthesizer
    description "Orchestrates code review using specialist agents as tools"
```

**The orchestrator instruction** guides the LLM through the workflow:
1. Fetch PR info and diff
2. Call `context_builder` to build PR-aware repo context
3. Chunk the diff
4. For each chunk:
   - Call `chunk_context_builder` for historical context (blame, issues)
   - Call specialists (`security_specialist`, `bug_specialist`, `quality_specialist`) with full context
5. Call `validator` to filter false positives
6. Call `synthesizer` to create final review

**Benefits of V3**:
- LLM flexibility for orchestration decisions
- Natural language workflow description
- Specialists as reusable tools

**Limitations**:
- Relies on LLM to correctly invoke tools in sequence
- Less deterministic than explicit flow control (V2)

---

## DSL Gaps and Proposed Extensions

### Gap 0: Flow-as-Tool

**Problem**: An agent cannot invoke a flow as a tool. Default agent instructions that say "run the main flow" are aspirational - there's no mechanism to actually invoke flows.

**Current Workaround**: Describe the workflow steps in the agent instruction and rely on the LLM to execute them using available tools.

**Proposed DSL Extension**:
```
# Expose a flow as a tool for agents
tool review_flow = flow main

agent:
    tools github, fs, review_flow
    instruction "Call review_flow to run the full review process"
```

**Grammar Addition**:
```lark
tool_definition: "tool" IDENTIFIER "=" "flow" IDENTIFIER  -> tool_from_flow
```

This would allow agents to invoke deterministic flow logic as a tool, getting the best of both worlds: LLM flexibility for orchestration decisions, with DSL precision for complex multi-step workflows.

---

### Gap 1: List Operations

**Problem**: No native list manipulation (filter, map, append, concat, length).

**Current Workaround**: Use LLM calls to process lists.

**Proposed DSL Extension**:
```
# List comprehension-style filtering
$high_confidence = [$f for $f in $findings if $f.confidence >= 80]

# Or function-style
$high_confidence = filter($findings, $f -> $f.confidence >= 80)

# Built-in operations
$merged = concat($list1, $list2)
$count = len($findings)
```

**Grammar Addition**:
```lark
// List comprehension
list_comprehension: LSQB expression "for" variable "in" expression ("if" condition)? RSQB

// Built-in functions
builtin_function: "filter" | "map" | "concat" | "len" | "sum" | "max" | "min"
```

### Gap 2: Parallel Result Aggregation

**Problem**: `parallel do` doesn't collect results into a single structure.

**Current Workaround**: Multiple `push` statements after parallel block.

**Proposed DSL Extension**:
```
# Parallel with automatic result collection
$results = parallel collect do
    $a = run agent reviewer1 $chunk
    $b = run agent reviewer2 $chunk
    $c = run agent reviewer3 $chunk
end
# $results = [$a, $b, $c]

# Or parallel map pattern
$reviews = parallel for $chunk in $chunks do
    $review = call llm reviewer $chunk
end
# $reviews = list of all review results
```

**Grammar Addition**:
```lark
parallel_block: "parallel" "do" ...                           -> parallel_fire_forget
              | "parallel" "collect" "do" ...                 -> parallel_collect
              | "parallel" "for" variable "in" expression "do" ... -> parallel_map
```

### Gap 3: Conditional Early Exit in Loops

**Problem**: No `break` statement for early loop termination.

**Current Workaround**: Use `loop max N` with condition-based `continue`.

**Proposed DSL Extension**:
```
for $finding in $findings do
    if $finding.severity == "error":
        $has_errors = true
        break
    end
end
```

**Grammar Addition**:
```lark
flow_control: "continue" | "abort" | "break" | "retry" "step" expression
```

### Gap 4: String Operations

**Problem**: No string split, join, contains, replace operations.

**Proposed DSL Extension**:
```
$lines = split($diff, "\n")
$combined = join($items, ", ")
$has_match = contains($text, "pattern")
$cleaned = replace($text, "old", "new")
```

### Gap 5: Aggregate Functions

**Problem**: No sum, average, max, min for lists.

**Proposed DSL Extension**:
```
$avg_confidence = avg($findings, $f -> $f.confidence)
$max_severity = max($findings, $f -> $f.severity)
$total_issues = count($findings)
```

### Gap 6: Typed Prompt Parameters

**Problem**: Prompts receive untyped `$var` references.

**Proposed DSL Extension**:
```
prompt reviewer ($context: RepoContext, $diff: string) expecting ReviewResult: """
Review the code with the provided context.
Context: $context.summary
Diff: $diff
"""
```

---

## Benchmark Methodology

### Benchmark Dataset Structure

Based on industry benchmarks (Greptile, Augment), we need:

```
benchmarks/
├── code-review/
│   ├── dataset.yaml           # Dataset manifest
│   ├── repos/                  # Cloned repositories
│   │   ├── sentry/
│   │   ├── grafana/
│   │   └── ...
│   └── cases/
│       ├── case_001/
│       │   ├── bug.yaml        # Bug description and ground truth
│       │   ├── before.patch    # Code before the bug fix
│       │   └── after.patch     # Code after the bug fix
│       └── ...
└── harness/
    ├── runner.py              # Test harness
    ├── evaluator.py           # Scoring logic
    └── report.py              # Report generation
```

### Dataset YAML Schema

```yaml
# dataset.yaml
name: "Streetrace Code Review Benchmark v1"
version: "1.0"
description: "50 real-world bug-fix PRs from open-source repositories"

repositories:
  - name: sentry
    url: https://github.com/getsentry/sentry
    language: python

  - name: grafana
    url: https://github.com/grafana/grafana
    language: go

cases:
  - id: "case_001"
    repo: sentry
    pr_number: 12345
    bug_type: "null_reference"
    severity: "high"
    ground_truth:
      file: "src/sentry/api/endpoints/auth.py"
      line: 142
      description: "Missing null check on user.email before access"
      category: "bug"
```

### Evaluation Metrics

```python
# evaluator.py pseudocode
def evaluate_review(review: ReviewResult, ground_truth: list[Bug]) -> Metrics:
    """Evaluate a code review against ground truth."""

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for finding in review.findings:
        if matches_ground_truth(finding, ground_truth):
            true_positives += 1
        else:
            false_positives += 1

    for bug in ground_truth:
        if not any(matches(f, bug) for f in review.findings):
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)
    f_score = 2 * (precision * recall) / (precision + recall)

    return Metrics(precision, recall, f_score, false_positives)
```

### Test Harness Integration

```yaml
# .streetrace/benchmarks.yaml
benchmarks:
  code-review:
    dataset: benchmarks/code-review/dataset.yaml
    agents:
      - name: "v1-monolithic"
        path: agents/code-review/v1-monolithic.sr

      - name: "v2-parallel"
        path: agents/code-review/v2-parallel.sr

      - name: "v3-hierarchical"
        path: agents/code-review/v3-hierarchical.sr

    models:
      - anthropic/claude-sonnet-4-5
      - anthropic/haiku
      - openai/gpt-4o

    output: benchmarks/results/
```

### Running Benchmarks

```bash
# Run all agent variants with all models
streetrace benchmark run code-review

# Run specific agent with specific model
streetrace benchmark run code-review --agent v2-parallel --model claude-sonnet

# Generate comparison report
streetrace benchmark report code-review --format markdown
```

---

## Validation Strategy

### The Validation Problem

LLM-generated findings suffer from:
- **Hallucinations**: LLM invents code that doesn't exist
- **Location errors**: Wrong file or line number
- **Pre-existing issues**: Flags unchanged code
- **Overcorrection bias**: Assumes flaws exist even when code is correct

Research shows prompting LLMs to "explain and propose fixes" increases misjudgment rates ([source](https://arxiv.org/html/2508.12358v1)).

### Solution: Tool-Equipped Validator Agent

Based on production patterns from [BitsAI-CR](https://arxiv.org/html/2501.15134v1) (75% precision) and [VulAgent](https://arxiv.org/abs/2509.11523) (36% FP reduction):

**Key insight**: The validator must have **tools to verify claims**, not just reason about them.

```
agent validator:
    tools github, fs  # CRITICAL: needs tools to read code, check diff
    instruction validator_instruction
    description "Validates findings by verifying code claims"
```

**Validation steps (hypothesis validation pattern)**:

1. **Verify Location Exists**: Read file at stated line - catch hallucinations
2. **Verify In Changed Code**: Check diff - filter pre-existing issues
3. **Check Defensive Code**: Search for guards - find false positives
4. **Verify Factual Claims**: Check types/imports - catch errors
5. **Assess Trigger Path**: Is there a realistic exploit/bug path?

**Reasoning pattern**: Use "Conclusion-First" (decision then rationale) for speed without accuracy loss.

**Decision**: Binary RETAIN/DISCARD - no score adjustment (avoids overcorrection).

---

## Scoring Calibration Strategy

### The Calibration Problem

Different reviewer agents may score confidence differently:
- Security reviewer: conservative (tends to under-score)
- Bug reviewer: aggressive (tends to over-score)
- Style reviewer: variable

### Solution: Two-Phase Calibration

**Phase 1: In-Prompt Calibration**
All reviewers share the same scoring rubric (see `scoring_rubric` prompt above).

**Phase 2: Post-Hoc Calibration**
After initial findings, run a calibration pass:

```
prompt calibrator: """You are a scoring calibrator.

Given findings from multiple reviewers, normalize their confidence scores
to a consistent scale:

1. Compare similar findings across reviewers
2. Identify reviewers who score high/low
3. Adjust scores to match the rubric:
   - 90-100: Definite issue with clear evidence
   - 80-89: Likely issue with strong evidence
   - 70-79: Possible issue, needs context
   - <70: Don't report

Findings:
$all_findings

Return recalibrated findings with adjusted confidence scores.
"""

flow calibrate_scores $findings:
    $calibrated = call llm calibrator $findings
    return $calibrated
```

### Alternative: LLM-as-Jury

For highest precision, use multiple LLMs to vote on each finding:

```
flow validate_with_jury $finding $context:
    parallel do
        $vote1 = call llm validator $finding $context using model "claude-sonnet"
        $vote2 = call llm validator $finding $context using model "gpt-4o"
        $vote3 = call llm validator $finding $context using model "gemini-pro"
    end

    # Majority vote
    $votes = [$vote1.validated, $vote2.validated, $vote3.validated]
    $approved = count_true($votes) >= 2

    return { finding: $finding, approved: $approved }
```

---

## Implementation Roadmap

### Phase 1: Core DSL Extensions (Required)

1. **List `push` operation** - Already in grammar, verify runtime works
2. **Parallel result collection** - Extend `parallel_block` in codegen
3. **List filtering** - Add `filter()` builtin function

### Phase 2: Agent Implementation

1. Implement V1 (monolithic) as baseline
2. Implement V2 (parallel) as primary
3. Implement V3 (hierarchical) as comparison

### Phase 3: Benchmark Infrastructure

1. Curate 50-case dataset from public bug-fix PRs
2. Implement test harness runner
3. Implement evaluation metrics
4. Create reporting dashboard

### Phase 4: Optimization

1. Tune prompts based on benchmark results
2. Calibrate scoring thresholds
3. Optimize chunk sizes and context retrieval
4. A/B test model combinations

---

## Appendix A: Existing DSL Capabilities Inventory

| Feature | Status | Notes |
|---------|--------|-------|
| `parallel do` | ✅ Works | Fire-and-forget parallel |
| `for ... in` | ✅ Works | List iteration |
| `loop max N` | ✅ Works | Bounded loops |
| `match ... when` | ✅ Works | Pattern matching |
| `if ... :` | ✅ Works | Conditionals |
| `schema` | ✅ Works | Pydantic models |
| `expecting Schema` | ✅ Works | Validated LLM output |
| `push to` | ✅ Grammar | Needs runtime verification |
| `delegate` | ✅ Works | Routing (sub-agent takes over) |
| `use` | ✅ Works | Tool-use (parent calls sub-agents as tools) |
| `run agent` | ✅ Works | Agent invocation |
| `call llm` | ✅ Works | Direct LLM calls |
| `on escalate` | ✅ Works | Escalation handling |
| List filter | ❌ Missing | Needs extension |
| List concat | ❌ Missing | Needs extension |
| String split | ❌ Missing | Needs extension |
| `break` | ❌ Missing | Needs extension |
| Parallel collect | ❌ Missing | Needs extension |

## Appendix B: Key Files Reference

| Component | Path |
|-----------|------|
| DSL Grammar | `src/streetrace/dsl/grammar/streetrace.lark` |
| AST Nodes | `src/streetrace/dsl/ast/nodes.py` |
| Code Generator | `src/streetrace/dsl/codegen/generator.py` |
| Flow Visitor | `src/streetrace/dsl/codegen/visitors/flows.py` |
| Runtime Context | `src/streetrace/dsl/runtime/context.py` |
| Workflow Base | `src/streetrace/dsl/runtime/workflow.py` |
| Example Agents | `agents/examples/dsl/*.sr` |

## Appendix C: Research References

- [Augment Benchmark (Dec 2025)](https://www.augmentcode.com/blog/we-benchmarked-7-ai-code-review-tools-on-real-world-prs-here-are-the-results)
- [Greptile Benchmark (Jul 2025)](https://www.greptile.com/benchmarks)
- [Confidence Calibration via Multi-Agent Deliberation](https://arxiv.org/html/2404.09127v3)
- [AutoSCORE Multi-Agent Scoring](https://arxiv.org/html/2509.21910v1)
- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
