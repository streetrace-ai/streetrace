# Code Review Agent Benchmark Design

## Overview

This document describes the benchmark infrastructure for evaluating Streetrace code review agents against industry-standard datasets.

## Benchmark Dataset

### Source: Adapted Industry Benchmarks

We adapt methodology from:
- **Greptile Benchmark**: 50 real-world bug-fix PRs across 5 repos
- **Augment Benchmark**: 50 PRs from large open-source projects

### Dataset Structure

```
benchmarks/
├── code-review/
│   ├── dataset.yaml           # Dataset manifest
│   ├── README.md              # Dataset documentation
│   │
│   ├── repos/                 # Repository snapshots
│   │   ├── sentry/            # Python - error tracking
│   │   ├── grafana/           # Go - monitoring
│   │   ├── calcom/            # TypeScript - scheduling
│   │   ├── discourse/         # Ruby - forums
│   │   └── keycloak/          # Java - identity
│   │
│   └── cases/                 # Individual test cases
│       ├── sentry-001/
│       │   ├── case.yaml      # Case metadata
│       │   ├── before/        # Code with bug
│       │   ├── after/         # Bug-fix code
│       │   └── ground_truth.yaml
│       ├── sentry-002/
│       └── ...
│
└── harness/
    ├── __init__.py
    ├── runner.py              # Test execution
    ├── evaluator.py           # Scoring logic
    ├── reporter.py            # Report generation
    └── cli.py                 # CLI interface
```

### Case YAML Schema

```yaml
# cases/sentry-001/case.yaml
id: "sentry-001"
repo: sentry
language: python
pr_number: 12345  # Original PR reference

bug:
  type: "null_reference"
  severity: "high"
  introduced_in: "abc1234"  # Commit that introduced bug
  fixed_in: "def5678"       # Commit that fixed bug

ground_truth:
  - file: "src/sentry/api/endpoints/auth.py"
    line_start: 142
    line_end: 145
    category: "bug"
    title: "Missing null check on user.email"
    description: |
      The code accesses user.email without checking if user is None,
      causing AttributeError when user is not authenticated.
    severity: "error"

metadata:
  source: "greptile-benchmark"
  created: "2025-01-15"
  difficulty: "medium"
```

### Dataset Manifest

```yaml
# dataset.yaml
name: "Streetrace Code Review Benchmark"
version: "1.0.0"
description: |
  50 real-world bug-fix PRs from open-source repositories.
  Ground truth verified by manual review.

repositories:
  sentry:
    url: "https://github.com/getsentry/sentry"
    language: python
    commit: "abc123..."  # Pinned commit
    cases: 10

  grafana:
    url: "https://github.com/grafana/grafana"
    language: go
    commit: "def456..."
    cases: 10

  calcom:
    url: "https://github.com/calcom/cal.com"
    language: typescript
    commit: "ghi789..."
    cases: 10

  discourse:
    url: "https://github.com/discourse/discourse"
    language: ruby
    commit: "jkl012..."
    cases: 10

  keycloak:
    url: "https://github.com/keycloak/keycloak"
    language: java
    commit: "mno345..."
    cases: 10

evaluation:
  metrics:
    - precision
    - recall
    - f_score
    - false_positive_rate

  matching:
    # How strict to be when matching findings to ground truth
    file_match: "exact"        # exact | prefix | fuzzy
    line_tolerance: 5          # Lines within N are a match
    category_required: true    # Must match bug/security/style
```

## Test Harness

### Runner Architecture

```python
# harness/runner.py
"""Benchmark test runner for code review agents."""

from dataclasses import dataclass
from pathlib import Path
import asyncio

@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    dataset_path: Path
    agents: list[str]           # Agent .sr file paths
    models: list[str]           # Model identifiers
    output_dir: Path
    parallel_cases: int = 5     # Run N cases in parallel
    timeout_seconds: int = 300  # Per-case timeout

@dataclass
class CaseResult:
    """Result from running one case."""
    case_id: str
    agent: str
    model: str
    findings: list[dict]        # Agent's findings
    ground_truth: list[dict]    # Expected findings
    latency_ms: int
    tokens_used: int
    error: str | None = None

async def run_benchmark(config: BenchmarkConfig) -> list[CaseResult]:
    """Run the complete benchmark suite."""
    results = []
    cases = load_cases(config.dataset_path)

    for agent_path in config.agents:
        for model in config.models:
            # Run cases with bounded parallelism
            semaphore = asyncio.Semaphore(config.parallel_cases)
            tasks = [
                run_case_with_limit(semaphore, case, agent_path, model)
                for case in cases
            ]
            case_results = await asyncio.gather(*tasks)
            results.extend(case_results)

    return results

async def run_case(case: dict, agent_path: str, model: str) -> CaseResult:
    """Run a single test case."""
    # 1. Set up case environment
    # 2. Create mock PR from before/after
    # 3. Run agent
    # 4. Collect findings
    # 5. Compare to ground truth
    ...
```

### Evaluator Logic

```python
# harness/evaluator.py
"""Evaluation metrics for code review benchmark."""

from dataclasses import dataclass

@dataclass
class Metrics:
    """Evaluation metrics for one agent/model combination."""
    precision: float      # TP / (TP + FP)
    recall: float         # TP / (TP + FN)
    f_score: float        # 2 * (P * R) / (P + R)
    false_positive_rate: float
    true_positives: int
    false_positives: int
    false_negatives: int
    total_findings: int
    total_ground_truth: int

def evaluate_results(results: list[CaseResult], config: dict) -> Metrics:
    """Evaluate all results and compute metrics."""
    tp = fp = fn = 0

    for result in results:
        case_tp, case_fp, case_fn = evaluate_case(
            result.findings,
            result.ground_truth,
            config
        )
        tp += case_tp
        fp += case_fp
        fn += case_fn

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return Metrics(
        precision=precision,
        recall=recall,
        f_score=f_score,
        false_positive_rate=fp / (fp + tp) if (fp + tp) > 0 else 0,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        total_findings=tp + fp,
        total_ground_truth=tp + fn,
    )

def evaluate_case(
    findings: list[dict],
    ground_truth: list[dict],
    config: dict,
) -> tuple[int, int, int]:
    """Evaluate a single case. Returns (TP, FP, FN)."""
    matched_truth = set()
    matched_findings = set()

    line_tolerance = config.get("line_tolerance", 5)

    for i, finding in enumerate(findings):
        for j, truth in enumerate(ground_truth):
            if j in matched_truth:
                continue

            if matches(finding, truth, line_tolerance):
                matched_truth.add(j)
                matched_findings.add(i)
                break

    tp = len(matched_findings)
    fp = len(findings) - tp
    fn = len(ground_truth) - len(matched_truth)

    return tp, fp, fn

def matches(finding: dict, truth: dict, line_tolerance: int) -> bool:
    """Check if a finding matches a ground truth entry."""
    # File must match
    if finding.get("file") != truth.get("file"):
        return False

    # Line must be within tolerance
    finding_line = finding.get("line_start", finding.get("line", 0))
    truth_line = truth.get("line_start", truth.get("line", 0))
    if abs(finding_line - truth_line) > line_tolerance:
        return False

    # Category should match (if required)
    if finding.get("category") != truth.get("category"):
        return False

    return True
```

### Report Generation

```python
# harness/reporter.py
"""Generate benchmark reports."""

def generate_markdown_report(
    metrics_by_variant: dict[str, Metrics],
    output_path: Path,
) -> None:
    """Generate a markdown comparison report."""

    report = """# Code Review Benchmark Results

## Summary

| Agent | Model | Precision | Recall | F-Score | FP Rate |
|-------|-------|-----------|--------|---------|---------|
"""

    for variant, metrics in sorted(
        metrics_by_variant.items(),
        key=lambda x: x[1].f_score,
        reverse=True
    ):
        agent, model = variant.split("::")
        report += f"| {agent} | {model} | "
        report += f"{metrics.precision:.1%} | "
        report += f"{metrics.recall:.1%} | "
        report += f"{metrics.f_score:.1%} | "
        report += f"{metrics.false_positive_rate:.1%} |\n"

    report += """
## Analysis

### Best F-Score
...

### Precision vs Recall Trade-off
...

### Per-Category Performance
...
"""

    output_path.write_text(report)
```

## CLI Interface

```bash
# Initialize benchmark dataset
streetrace benchmark init code-review

# Run benchmark with all configured agents and models
streetrace benchmark run code-review

# Run specific agent/model combination
streetrace benchmark run code-review \
  --agent agents/code-review/v2-parallel.sr \
  --model anthropic/claude-sonnet-4-5

# Generate comparison report
streetrace benchmark report code-review \
  --format markdown \
  --output benchmarks/results/report.md

# Compare two specific runs
streetrace benchmark compare \
  results/run-001.json \
  results/run-002.json
```

## Configuration

```yaml
# .streetrace/benchmarks.yaml
benchmarks:
  code-review:
    dataset: benchmarks/code-review/dataset.yaml

    agents:
      v1-monolithic:
        path: agents/code-review/v1-monolithic.sr
        description: "Baseline single-pass reviewer"

      v2-parallel:
        path: agents/code-review/v2-parallel.sr
        description: "Production multi-agent reviewer"

      v3-hierarchical:
        path: agents/code-review/v3-hierarchical.sr
        description: "ADK delegation pattern"

    models:
      - anthropic/claude-sonnet-4-5
      - anthropic/haiku
      - openai/gpt-4o

    settings:
      parallel_cases: 5
      timeout_seconds: 300
      retry_on_error: 2

    output:
      dir: benchmarks/results/
      format: json
      keep_runs: 10
```

## Expected Results

Based on industry benchmarks, target performance:

| Metric | Target | Industry Average |
|--------|--------|------------------|
| Precision | >60% | 20-68% |
| Recall | >50% | 34-55% |
| F-Score | >55% | 25-59% |
| False Positive Rate | <10% | 5-15% |

## Integration with CI

```yaml
# .github/workflows/benchmark.yml
name: Code Review Benchmark

on:
  push:
    paths:
      - 'agents/code-review/**'
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: poetry install

      - name: Run benchmark
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          poetry run streetrace benchmark run code-review \
            --output benchmarks/results/ci-${{ github.sha }}.json

      - name: Generate report
        run: |
          poetry run streetrace benchmark report code-review \
            --format markdown \
            --output benchmarks/results/report.md

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmarks/results/

      - name: Check regression
        run: |
          poetry run streetrace benchmark check-regression \
            --baseline benchmarks/baseline.json \
            --current benchmarks/results/ci-${{ github.sha }}.json \
            --threshold 0.05  # Fail if F-score drops more than 5%
```

## Creating Test Cases

### From Real Bug-Fix PRs

```bash
# Find bug-fix PRs in a repository
gh pr list --repo getsentry/sentry \
  --label "bug" --state merged \
  --limit 50 --json number,title,body

# For each interesting PR:
# 1. Identify the bug-introducing commit
# 2. Create before/after snapshots
# 3. Write ground truth YAML
# 4. Verify with manual review
```

### Ground Truth Guidelines

A valid ground truth entry must:
1. **Be in changed code**: Not a pre-existing issue
2. **Be actionable**: Clear fix available
3. **Have real impact**: Not a theoretical concern
4. **Be verifiable**: Human can confirm the issue

### Case Difficulty Levels

- **Easy**: Single-line, obvious bugs (null check, typo)
- **Medium**: Multi-line, requires context understanding
- **Hard**: Architectural issues, security vulnerabilities, race conditions
