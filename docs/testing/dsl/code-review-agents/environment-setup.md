# Code Review Agents - Environment Setup

This document describes the environment setup required for manual end-to-end testing of
the code review agents and the DSL features they use.

## Prerequisites

### 1. Python Environment

Ensure StreetRace is installed with development dependencies:

```bash
cd /path/to/streetrace
poetry install
```

### 2. API Keys

The code review agents require working LLM and GitHub API access:

```bash
# Anthropic (required for code review agents)
export ANTHROPIC_API_KEY="your-key-here"

# GitHub token for PR access
export GITHUB_TOKEN="your-github-pat-here"
```

### 3. GitHub Token Permissions

The GitHub token needs the following permissions:

- `repo` - Full repository access (for private repos) or `public_repo` (for public repos)
- `read:org` - If reviewing PRs in organization repositories

### 4. Log Level (Optional)

For detailed debugging, enable debug logging:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
```

## Agent Files Location

The code review agents are located at:

```
agents/code-review/
├── v1-monolithic.sr    # Single-pass review with parallel fetch
├── v2-parallel.sr      # Multi-agent with parallel specialists
└── v3-hierarchical.sr  # LLM orchestration with sub-agents as tools
```

## Verifying Setup

### Check DSL Compilation

```bash
# Verify all agents compile correctly
poetry run streetrace check agents/code-review/v1-monolithic.sr
poetry run streetrace check agents/code-review/v2-parallel.sr
poetry run streetrace check agents/code-review/v3-hierarchical.sr

# Expected output for each: "agents/code-review/vX-xxx.sr: OK"
```

### Verify Generated Code

Inspect the generated Python code for each agent:

```bash
# View generated Python for V1
poetry run streetrace dump-python agents/code-review/v1-monolithic.sr

# Check parallel block code generation
poetry run streetrace dump-python agents/code-review/v2-parallel.sr | grep -A 20 "_parallel_specs"
```

### Verify GitHub Access

Test GitHub API access with a simple query:

```bash
# Using gh CLI
gh api repos/streetrace-ai/streetrace/pulls/1

# Or curl
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/streetrace-ai/streetrace/pulls
```

## Test Repositories

For testing, you can use:

1. **Public Test PRs**: Any public repository with open PRs
2. **StreetRace PRs**: PRs in the streetrace-ai/streetrace repository
3. **Local PRs**: PRs in repositories you have access to

### Example Test PRs

Create or identify test PRs with various characteristics:

| PR Type | Characteristics | Test Focus |
|---------|-----------------|------------|
| Simple | Single file, small change | Basic flow |
| Security | Contains potential vulnerabilities | Security specialist |
| Multi-file | Changes across multiple files | Chunking and parallel review |
| Complex | Large diff, multiple concerns | Full pipeline |

## DSL Features Used by Code Review Agents

The agents exercise these DSL features:

### V1 Monolithic

| Feature | Usage | Location |
|---------|-------|----------|
| `parallel do` | Fetch PR info and diff concurrently | Line 139-142 |
| `filter ... where` | Filter low-confidence findings | Line 159 |
| Property assignment | Update `$review.findings` | Line 160 |
| Object literals | Build `$full_context` | Line 149-152 |

### V2 Parallel

| Feature | Usage | Location |
|---------|-------|----------|
| `parallel do` | Multiple parallel blocks | Lines 495-498, 525-529 |
| `filter ... where` | Confidence and fixability filters | Lines 562, 587 |
| List concatenation | Combine findings with `+` | Lines 532-534 |
| Property access | Access nested schema fields | Throughout |

### V3 Hierarchical

| Feature | Usage | Location |
|---------|-------|----------|
| `use` keyword | Sub-agents as tools | Line 363 |
| Schema definitions | Structured outputs | Lines 20-37 |
| Agent definitions | Multiple specialists | Lines 78-262 |

## Environment Variables Summary

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API access for LLM calls |
| `GITHUB_TOKEN` | Yes | GitHub API access for PR data |
| `STREETRACE_LOG_LEVEL` | No | Log verbosity (`DEBUG`, `INFO`) |

## Test Input Preparation

### Identify Test PR

Choose a PR URL for testing:

```bash
# Example: Public PR
PR_URL="https://github.com/owner/repo/pull/123"

# Or just PR number with repo context
PR_INPUT="Review PR #123 in owner/repo"
```

### Create Test Input File

For reproducible testing, create an input file:

```bash
cat > /tmp/test-input.txt << 'EOF'
Review PR https://github.com/streetrace-ai/streetrace/pull/145
Focus on security issues.
EOF
```

## Reference Documents

- `docs/tasks/code-review-agent/dsl-implementation/tasks.md`: Design specification, 2026-01-27
- `docs/dev/dsl/parallel-execution.md`: Parallel block developer docs, 2026-01-27
- `docs/dev/dsl/filter-expression.md`: Filter expression developer docs, 2026-01-27
- `docs/user/dsl/flow-control.md`: Flow control user guide, 2026-01-27
- `docs/user/dsl/expressions.md`: Expressions user guide, 2026-01-27
