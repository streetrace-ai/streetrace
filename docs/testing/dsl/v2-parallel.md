# V2 Parallel Code Reviewer - Test Plan

This document defines validation expectations for the `agents/code-review/v2-parallel.sr` multi-agent code reviewer. Use these expectations to validate agent behavior against verbose logs.

## Test Execution

Run the agent with verbose logging:

```bash
poetry run streetrace --workload agents/code-review/v2-parallel.sr --verbose
```

Then provide a PR URL or number when prompted.

---

## Validation Expectations

### Phase 1: PR Context Fetching

**Agent:** `pr_context_fetcher`

**Expected Behavior:**
- Runs exactly once
- Output contains: PR number, title, description, state, base/head refs, author info
- Output contains: Project context (README summary, coding standards)

**Log Patterns to Find:**
```
Phase 1: Fetch project description and PR Info -> text...
```

**Validation Checklist:**
- [ ] Agent starts and completes without error
- [ ] Output includes PR metadata (number, title, description)
- [ ] Output includes project context summary

---

### Phase 2: Diff Chunking

**Agent:** `diff_chunker`

**Expected Behavior:**
- Runs exactly once
- Output is `DiffChunk[]` with at least 1 chunk (unless empty PR)
- Each chunk has non-empty: `title`, `description`, `git_diff_patch`
- All changed files appear in exactly one chunk (no duplicates, no missing)
- Chunk count is reasonable: `total_changed_lines / 2000` gives expected range

**Log Patterns to Find:**
```
Phase 2: Get Diff Chunks -> DiffChunk[]...
Phase 2 Complete: Created N chunks
```

**Validation Checklist:**
- [ ] Agent returns valid JSON array
- [ ] Each chunk has required fields (title, description, git_diff_patch)
- [ ] Chunk count logged
- [ ] All PR files covered by exactly one chunk

---

### Phase 3: Requirements Fetching

**Agent:** `requirements_fetcher`

**Expected Behavior:**
- Runs exactly once
- Output is text describing functional/non-functional requirements

**Log Patterns to Find:**
```
Phase 3: Fetch requirements -> text...
```

**Validation Checklist:**
- [ ] Agent starts and completes without error
- [ ] Output contains requirements relevant to PR

---

### Phase 4-5: Per-Chunk Processing Loop

**Agents:** `chunk_context_builder`, `security_reviewer_agent`, `bug_reviewer_agent`, `style_reviewer_agent`

**Expected Behavior:**
- Loop runs exactly N times where N = number of chunks from Phase 2
- Per iteration:
  - `chunk_context_builder` runs once (Phase 4)
  - All 3 reviewers run in parallel (Phase 5):
    - `security_reviewer_agent` produces `security_findings: Finding[]`
    - `bug_reviewer_agent` produces `bug_findings: Finding[]`
    - `style_reviewer_agent` produces `style_findings: Finding[]`
  - Findings accumulated: `findings = findings + security_findings + bug_findings + style_findings`

**Log Patterns to Find:**
```
Phase 4 [CHUNK LOOP]: Build historical context
Phase 5 [CHUNK LOOP]: Run analyzers
Processing chunk M/N: <chunk title>
Chunk findings - security: X, bugs: Y, style: Z
Total accumulated findings: T
```

**Validation Checklist:**
- [ ] Loop iterations = chunk count
- [ ] Each iteration logs chunk number and title
- [ ] All 3 reviewers run per chunk (check parallel execution)
- [ ] Each reviewer returns `Finding[]` (possibly empty)
- [ ] Findings accumulate correctly across chunks
- [ ] Each Finding has required fields: file, line_start, severity, category, title, description, confidence, reasoning

---

### Phase 6: Validation Flow

**Flow:** `validate_all`
**Agent:** `validator`

**Expected Behavior:**
- Flow runs once
- Filters to findings where `confidence >= 80`
- For each high-confidence finding:
  - `validator` agent runs with finding as input
  - Returns `ValidationResult` with: `valid: bool`, `reason: string`, `verification_steps: list[string]`
  - If `valid=true`, finding added to `validated_findings`

**Log Patterns to Find:**
```
[validate_all] Starting validation flow
[validate_all] Filtered to high-confidence findings
[validate_all] High-confidence findings to validate: N
[validate_all] [AGENT] Starting: validator
[validate_all] [AGENT] Completed: validator
[validate_all] Finding validation result: valid=true/false
[validate_all] Validation complete
[validate_all] Validated findings count: M
```

**Validation Checklist:**
- [ ] Only findings with confidence >= 80 are validated
- [ ] Validator runs once per high-confidence finding
- [ ] Each validation returns valid boolean and reason
- [ ] Valid findings count logged
- [ ] validated_findings count <= high_confidence count

---

### Phase 7: Deduplication

**Prompt:** `deduplicator`

**Expected Behavior:**
- LLM call runs once
- Input: `validated_findings` array
- Output: deduplicated `Finding[]`
- Output count <= input count

**Log Patterns to Find:**
```
Phase 7: Deduplicating...
Phase 7: Deduplicating N findings...
Phase 7 Complete: M unique findings after deduplication
```

**Validation Checklist:**
- [ ] Input count logged
- [ ] Output count logged
- [ ] Output count <= input count
- [ ] No duplicate findings in output (same file + line_start + title = duplicate)

---

### Phase 8: Patch Generation

**Flow:** `generate_all_patches`
**Agent:** `patch_generator`

**Expected Behavior:**
- Flow runs once
- Filters to findings where `suggested_fix != null`
- For each fixable finding:
  - `patch_generator` agent runs
  - Returns `Patch` with: `file`, `line_start`, `line_end`, `diff`, `confidence`, `can_fix_in_place`
  - If `can_fix_in_place=true`, patch added to `patches`

**Log Patterns to Find:**
```
[generate_all_patches] Starting patch generation flow
[generate_all_patches] Fixable findings count: N
[generate_all_patches] [AGENT] Starting: patch_generator
[generate_all_patches] [AGENT] Completed: patch_generator
[generate_all_patches] Patch result: can_fix_in_place=true/false
[generate_all_patches] Patch generation complete
[generate_all_patches] Generated patches count: M
```

**Validation Checklist:**
- [ ] Only findings with suggested_fix != null processed
- [ ] Fixable count logged
- [ ] Each patch has required fields
- [ ] Final patches count logged
- [ ] All patches have can_fix_in_place=true

---

### Phase 9: Final Compilation

**Prompt:** `final_compiler`

**Expected Behavior:**
- LLM call runs once
- Output is `FinalReview` schema with:
  - `summary: string` (2-3 sentences)
  - `findings: list[Finding]` (sorted by severity)
  - `patches: list[Patch]`
  - `recommendation: string` (one of: approve, request_changes, comment)
  - `overall_confidence: int`
  - `stats: string`

**Log Patterns to Find:**
```
Phase 9: Compiling final review...
Phase 9 Complete: N findings, M patches
Recommendation: <value>, Confidence: <score>
Review complete!
```

**Validation Checklist:**
- [ ] Output matches FinalReview schema
- [ ] Summary is 2-3 sentences
- [ ] Findings sorted by severity (error > warning > notice)
- [ ] Recommendation is valid value
- [ ] Confidence is 0-100 integer
- [ ] Stats string present

---

## End-to-End Invariants

These invariants should hold across the entire execution:

### 1. No Findings Lost
All findings from reviewers flow through:
`reviewers → accumulation → validation (filtered by confidence) → deduplication → final review`

**Validation:**
- Sum of all reviewer findings = total accumulated
- validated_findings <= high_confidence findings
- deduplicated <= validated_findings
- final.findings = deduplicated findings

### 2. Schema Compliance
Each agent output matches its `expecting` schema:

| Agent/Prompt | Expected Schema |
|--------------|-----------------|
| `security_reviewer` | `Finding[]` |
| `bug_reviewer` | `Finding[]` |
| `style_reviewer` | `Finding[]` |
| `validator_instruction` | `ValidationResult` |
| `patch_generator_instruction` | `Patch` |
| `deduplicator` | `Finding[]` |
| `diff_chunker_instruction` | `DiffChunk[]` |
| `final_compiler` | `FinalReview` |

**Validation:**
- No schema validation errors in logs
- All outputs parse as valid JSON matching schema

### 3. Parallel Execution Correctness
All 3 reviewers run for every chunk (none skipped):

**Validation:**
- Count of "security_reviewer_agent" executions = chunk count
- Count of "bug_reviewer_agent" executions = chunk count
- Count of "style_reviewer_agent" executions = chunk count

### 4. Retry on Schema Failure
If an agent returns prose instead of JSON, retry should occur:

**Validation:**
- Look for: `"validation failed, retrying"` in logs
- After retry, valid JSON returned or empty fallback used
- Warning logged if retry also fails

---

## Required Log Additions

To fully validate all expectations, add these log statements to `v2-parallel.sr`:

```dsl
# After Phase 2 (after diff_chunker):
log "Phase 2 Complete: Created ${len(diff_chunks)} chunks"

# In chunk loop start:
log "Processing chunk ${chunk_index}/${chunk_count}: ${chunk.title}"

# After parallel reviewers:
log "Chunk findings - security: ${len(security_findings)}, bugs: ${len(bug_findings)}, style: ${len(style_findings)}"
log "Total accumulated findings: ${len(findings)}"

# In validate_all, after filter:
log "[validate_all] High-confidence findings to validate: ${len(high_confidence)}"

# In validate_all, after each validation:
log "[validate_all] Finding validation result: valid=${result.valid}"

# In validate_all, at end:
log "[validate_all] Validated findings count: ${len(validated_findings)}"

# Before Phase 7:
log "Phase 7: Deduplicating ${len(validated_findings)} findings..."

# After Phase 7:
log "Phase 7 Complete: ${len(findings)} unique findings after deduplication"

# In generate_all_patches, after filter:
log "[generate_all_patches] Fixable findings count: ${len(fixable)}"

# In generate_all_patches, after each patch:
log "[generate_all_patches] Patch result: can_fix_in_place=${patch.can_fix_in_place}"

# In generate_all_patches, at end:
log "[generate_all_patches] Generated patches count: ${len(patches)}"

# After Phase 9:
log "Phase 9 Complete: ${len(final.findings)} findings, ${len(final.patches)} patches"
log "Recommendation: ${final.recommendation}, Confidence: ${final.overall_confidence}"
```

---

## Test Scenarios

### Scenario 1: Small PR (< 2000 lines)
- Single chunk expected
- All phases run once per chunk
- Validates basic flow

### Scenario 2: Large PR (> 2000 lines)
- Multiple chunks expected
- Validates chunk loop iteration
- Validates finding accumulation across chunks

### Scenario 3: Clean PR (no issues)
- Reviewers return empty Finding[]
- Validation, deduplication, patch generation handle empty inputs
- Final review has 0 findings, recommendation = "approve"

### Scenario 4: PR with Security Issues
- Security reviewer returns high-confidence findings
- Validator confirms findings
- Patches generated for fixable issues
- Recommendation = "request_changes"

### Scenario 5: Schema Validation Retry
- Simulate agent returning prose
- Verify retry occurs
- Verify fallback to empty array on double failure
- Verify warning logged

---

## Failure Modes to Watch

1. **Agent returns prose instead of JSON**: Should trigger retry, then fallback
2. **Empty diff_chunks**: Loop should not execute, final review should be empty
3. **All findings below confidence 80**: validated_findings empty, patches empty
4. **No suggested_fix on any finding**: patches array empty
5. **Validator tools fail**: Should log error, finding marked invalid
6. **Parallel agent timeout**: Should log timeout, partial results used
