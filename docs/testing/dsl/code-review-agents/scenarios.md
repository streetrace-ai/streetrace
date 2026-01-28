# Code Review Agents - Test Scenarios

This document describes manual end-to-end test scenarios for the code review agents
and the DSL features they demonstrate.

## Feature Scope

The code review agents exercise these DSL features:

1. **Parallel blocks** - `parallel do` with `run agent` statements
2. **Filter expressions** - `filter $list where .property >= value`
3. **Property assignment** - `$obj.property = $value`
4. **List concatenation** - `$list + $list` with `+` operator
5. **Object literals** - `{ key: $value, key2: value2 }`

## User Journeys

### Journey 1: Run V1 Monolithic Code Review

A user wants to run a simple, single-pass code review on a PR.

**Steps**:
1. Set environment variables (API keys)
2. Run V1 agent with a PR URL
3. Verify structured review output with findings

### Journey 2: Run V2 Parallel Code Review

A user wants comprehensive review with specialized parallel reviewers.

**Steps**:
1. Set environment variables
2. Run V2 agent with a PR URL
3. Verify parallel specialists execute
4. Verify findings are combined, filtered, and validated

### Journey 3: Run V3 Hierarchical Code Review

A user wants LLM-orchestrated review using sub-agents as tools.

**Steps**:
1. Set environment variables
2. Run V3 agent with a PR URL
3. Verify orchestrator delegates to specialists
4. Verify final synthesized review

---

## Scenario 1: Parallel Block Execution

**Feature**: `parallel do` executes agents concurrently.

### Scenario 1.1: V1 Parallel Fetch

**Input DSL** (excerpt from `v1-monolithic.sr`):
```streetrace
parallel do
    $pr_info = run agent pr_fetcher $input
    $diff = run agent diff_fetcher $input
end
```

**Test Command**:
```bash
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run \
    agents/code-review/v1-monolithic.sr \
    --input "Review PR https://github.com/owner/repo/pull/123"
```

**Expected Behavior**:
1. Both agents start concurrently (check DEBUG logs)
2. Both results are assigned after completion
3. Flow continues with both `$pr_info` and `$diff` available

**Log Output to Check**:
```
DEBUG ... Parallel block - execute agents concurrently
DEBUG ... Running agent: pr_fetcher
DEBUG ... Running agent: diff_fetcher
```

**Verification**:
1. Check that `pr_fetcher` and `diff_fetcher` logs appear close together (concurrent start)
2. Verify no errors about missing variables after the parallel block

### Scenario 1.2: V2 Parallel Specialists

**Input DSL** (excerpt from `v2-parallel.sr`):
```streetrace
parallel do
    $security_findings = run agent security_reviewer_agent $full_context $chunk
    $bug_findings = run agent bug_reviewer_agent $full_context $chunk
    $style_findings = run agent style_reviewer_agent $full_context $chunk
end
```

**Test Command**:
```bash
STREETRACE_LOG_LEVEL=DEBUG poetry run streetrace run \
    agents/code-review/v2-parallel.sr \
    --input "Review PR https://github.com/owner/repo/pull/123"
```

**Expected Behavior**:
1. All three specialist agents start concurrently
2. Results are collected into respective variables
3. Findings from all specialists are available for combination

**Verification**:
1. Check DEBUG logs show three agents running in the same parallel block
2. Verify combined findings include all categories (security, bug, style)

---

## Scenario 2: Filter Expression

**Feature**: `filter $list where .property >= value` filters lists.

### Scenario 2.1: Confidence Filtering (V1)

**Input DSL** (excerpt from `v1-monolithic.sr`):
```streetrace
$filtered = filter $review.findings where .confidence >= 80
$review.findings = $filtered
```

**Verification via Generated Code**:
```bash
poetry run streetrace dump-python agents/code-review/v1-monolithic.sr | grep -A 2 "filter"
```

**Expected Generated Code**:
```python
ctx.vars['filtered'] = [_item for _item in ctx.vars['review']['findings'] if _item['confidence'] >= 80]
ctx.vars['review']['findings'] = ctx.vars['filtered']
```

**Test Command**:
```bash
poetry run streetrace run \
    agents/code-review/v1-monolithic.sr \
    --input "Review PR https://github.com/owner/repo/pull/123"
```

**Expected Output**:
- Only findings with `confidence >= 80` in final output
- Lower confidence findings filtered out

### Scenario 2.2: Null Check Filtering (V2)

**Input DSL** (excerpt from `v2-parallel.sr`):
```streetrace
$fixable = filter $findings where .suggested_fix != null
```

**Verification via Generated Code**:
```bash
poetry run streetrace dump-python agents/code-review/v2-parallel.sr | grep "suggested_fix"
```

**Expected Generated Code**:
```python
ctx.vars['fixable'] = [_item for _item in ctx.vars['findings'] if _item['suggested_fix'] != None]
```

**Expected Behavior**:
- Findings without `suggested_fix` are excluded from patch generation
- Only fixable findings proceed to patch generator

---

## Scenario 3: List Concatenation

**Feature**: `$list + $list` concatenates lists.

### Scenario 3.1: Combining Specialist Findings (V2)

**Input DSL** (excerpt from `v2-parallel.sr`):
```streetrace
$all_findings = $all_findings + $security_findings.findings
$all_findings = $all_findings + $bug_findings.findings
$all_findings = $all_findings + $style_findings.findings
```

**Verification via Generated Code**:
```bash
poetry run streetrace dump-python agents/code-review/v2-parallel.sr | grep -A 3 "all_findings"
```

**Expected Generated Code**:
```python
ctx.vars['all_findings'] = (ctx.vars['all_findings'] + ctx.vars['security_findings']['findings'])
ctx.vars['all_findings'] = (ctx.vars['all_findings'] + ctx.vars['bug_findings']['findings'])
ctx.vars['all_findings'] = (ctx.vars['all_findings'] + ctx.vars['style_findings']['findings'])
```

### Scenario 3.2: Appending Single Items

**Input DSL** (excerpt from `v2-parallel.sr`):
```streetrace
$validated = $validated + [$finding]
```

**Verification**:
1. Single items wrapped in list literals
2. List grows correctly in loop

---

## Scenario 4: Property Assignment

**Feature**: `$obj.property = $value` assigns to object properties.

### Scenario 4.1: Update Review Findings (V1)

**Input DSL**:
```streetrace
$review.findings = $filtered
```

**Verification via Generated Code**:
```bash
poetry run streetrace dump-python agents/code-review/v1-monolithic.sr | grep "review.*findings.*="
```

**Expected Generated Code**:
```python
ctx.vars['review']['findings'] = ctx.vars['filtered']
```

**Expected Behavior**:
- Original `$review` object is modified in place
- `findings` property is updated to filtered list
- Other properties of `$review` (like `summary`) remain intact

---

## Scenario 5: Object Literals

**Feature**: `{ key: $value }` creates object literals.

### Scenario 5.1: Build Context Object (V1)

**Input DSL** (excerpt from `v1-monolithic.sr`):
```streetrace
$full_context = {
    pr: $pr_info,
    repo_and_history: $context
}
```

**Verification via Generated Code**:
```bash
poetry run streetrace dump-python agents/code-review/v1-monolithic.sr | grep -A 3 "full_context"
```

**Expected Generated Code**:
```python
ctx.vars['full_context'] = {"pr": ctx.vars['pr_info'], "repo_and_history": ctx.vars['context']}
```

### Scenario 5.2: Build Validation Context (V2)

**Input DSL** (excerpt from `v2-parallel.sr`):
```streetrace
$validation_context = {
    diff: $diff,
    pr_description: $pr_info.description,
    changes_summary: $pr_info.title
}
```

**Expected Behavior**:
- Object created with values from different sources
- Nested property access works in object literal values

---

## Scenario 6: Full End-to-End Tests

### Scenario 6.1: V1 Complete Review

**Test Command**:
```bash
poetry run streetrace run \
    agents/code-review/v1-monolithic.sr \
    --input "Review PR https://github.com/streetrace-ai/streetrace/pull/145"
```

**Expected Output Structure**:
```json
{
  "summary": "...",
  "findings": [...],
  "recommendation": "approve|request_changes|comment",
  "confidence_score": 85
}
```

**Verification Checklist**:
- [ ] Parallel fetch completes (pr_info and diff obtained)
- [ ] Context building runs
- [ ] Review generates findings
- [ ] Filter removes findings with confidence < 80
- [ ] Final output matches `ReviewResult` schema

### Scenario 6.2: V2 Complete Review

**Test Command**:
```bash
poetry run streetrace run \
    agents/code-review/v2-parallel.sr \
    --input "Review PR https://github.com/streetrace-ai/streetrace/pull/145"
```

**Expected Output Structure**:
```json
{
  "summary": "...",
  "findings": [...],
  "patches": [...],
  "recommendation": "...",
  "overall_confidence": 87,
  "stats": "..."
}
```

**Verification Checklist**:
- [ ] Initial parallel fetch completes
- [ ] Diff is chunked
- [ ] Each chunk gets historical context
- [ ] Parallel specialists run for each chunk
- [ ] Findings are combined with `+` operator
- [ ] Findings are filtered by confidence
- [ ] Validation reduces false positives
- [ ] Patch generation runs for fixable findings
- [ ] Final output matches `FinalReview` schema

### Scenario 6.3: V3 Hierarchical Review

**Test Command**:
```bash
poetry run streetrace run \
    agents/code-review/v3-hierarchical.sr \
    --input "Review PR https://github.com/streetrace-ai/streetrace/pull/145"
```

**Expected Behavior**:
- Orchestrator uses sub-agents as tools
- Specialist calls visible in logs
- Synthesizer produces final review

**Verification Checklist**:
- [ ] Orchestrator receives PR input
- [ ] Context builder called as tool
- [ ] Specialist agents called as tools
- [ ] Validator called as tool
- [ ] Final review is synthesized

---

## Scenario 7: Error Cases

### Scenario 7.1: Invalid Parallel Block Contents

Create a test file with invalid parallel block:

```streetrace
# test_invalid_parallel.sr
flow main:
    parallel do
        $x = 42  # Assignment not allowed
    end
```

**Test Command**:
```bash
poetry run streetrace check test_invalid_parallel.sr
```

**Expected Error**:
```
TypeError: parallel do only supports 'run agent' statements. Found: Assignment
```

### Scenario 7.2: Missing GitHub Token

**Test Command**:
```bash
unset GITHUB_TOKEN
poetry run streetrace run \
    agents/code-review/v1-monolithic.sr \
    --input "Review PR https://github.com/owner/repo/pull/1"
```

**Expected Behavior**:
- Error related to GitHub API authentication
- Workflow fails with clear error message

---

## Troubleshooting

### Parallel Block Not Executing Concurrently

**Symptoms**: Agents appear to run sequentially in logs.

**Debug Steps**:
1. Check generated code:
   ```bash
   poetry run streetrace dump-python agents/code-review/v1-monolithic.sr | grep -A 20 "_parallel"
   ```
2. Verify `_execute_parallel_agents` is called
3. Check for any blocking operations before agents

### Filter Not Working

**Symptoms**: All findings returned, including low-confidence ones.

**Debug Steps**:
1. Check generated code for list comprehension:
   ```bash
   poetry run streetrace dump-python agents/code-review/v1-monolithic.sr | grep "_item for _item"
   ```
2. Verify schema field name matches filter condition
3. Check confidence values in raw response

### Property Assignment Error

**Symptoms**: `KeyError` when assigning to property.

**Debug Steps**:
1. Verify parent object exists before assignment
2. Check that LLM returned expected schema structure
3. Add logging to inspect variable contents before assignment

---

## Reference Documents

- `docs/tasks/code-review-agent/dsl-implementation/tasks.md`: Design specification, 2026-01-27
- `agents/code-review/v1-monolithic.sr`: V1 agent implementation, 2026-01-27
- `agents/code-review/v2-parallel.sr`: V2 agent implementation, 2026-01-27
- `agents/code-review/v3-hierarchical.sr`: V3 agent implementation, 2026-01-27
- `docs/dev/dsl/parallel-execution.md`: Parallel block developer docs, 2026-01-27
- `docs/dev/dsl/filter-expression.md`: Filter expression developer docs, 2026-01-27
- `docs/dev/dsl/property-assignment.md`: Property assignment developer docs, 2026-01-27
