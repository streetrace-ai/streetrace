# Step Executor Agent

The Step Executor Agent (StepExecutor) implements hybrid step-based execution to dramatically reduce token usage while maintaining autonomous code generation capabilities. This agent addresses the token efficiency problem described in [Issue #35](https://github.com/krmrn42/street-race/issues/35).

## Overview

Instead of sending full chat history with each LLM request (which can consume ~56k tokens), the Step Executor breaks down complex tasks into atomic steps that execute with minimal, targeted context (~4k tokens total - a 93% reduction).

## Key Features

- **90%+ Token Reduction**: Reduces token usage from ~56k to ~4k for complex tasks
- **Autonomous Layer Generation**: Maintains ability to generate complete software layers
- **Step-Based Decomposition**: Breaks tasks into focused, atomic steps
- **Minimal Context**: Each step receives only necessary context, not full history
- **Artifact Management**: Efficiently passes results between steps
- **Dependency Resolution**: Executes steps in proper order based on dependencies

## Architecture

### Core Components

1. **Orchestrator**: Manages overall execution flow and plan generation
2. **PlanGenerator**: Creates step-based execution plans from requirements
3. **StepExecutor**: Executes individual steps with minimal context
4. **Models**: Data structures for plans, steps, and execution results

### Step Types

- **ANALYZE**: Examine code, requirements, or project structure
- **GENERATE**: Create new code, files, or components  
- **MODIFY**: Update existing code or files
- **VALIDATE**: Test, verify, or quality-check work
- **CLEANUP**: Optimize, refactor, or clean up artifacts

## Usage

### As an Agent

```python
from streetrace.agents.step_executor.agent import StepExecutorAgent

# Create and use through StreetRace's agent system
agent = StepExecutorAgent()
# Agent will be available in StreetRace's agent discovery
```

### Direct Execution

```python
from streetrace.agents.step_executor.agent import run_step_executor

result = await run_step_executor(
    requirements="Create a user management system with authentication",
    model_factory=model_factory,
    system_context=system_context,
    tools=tools,
)
```

### Through StreetRace CLI

```bash
# The agent will be discoverable through the list_agents tool
streetrace --model=your-model
> list_agents()
> run_agent("StepExecutor", "Create a REST API with user management")
```

## Example Workflows

### 1. User Management System

**Traditional Approach**: ~56k tokens with full context
**Step-Based Approach**: ~4k tokens total

1. **ANALYZE**: Examine project structure and requirements (500 tokens)
2. **GENERATE**: Create user model and database schema (800 tokens)
3. **GENERATE**: Implement authentication service (900 tokens)
4. **GENERATE**: Create API endpoints (900 tokens)
5. **VALIDATE**: Test the implementation (600 tokens)
6. **CLEANUP**: Optimize and document (300 tokens)

### 2. Data Processing Pipeline

1. **ANALYZE**: Review data sources and requirements
2. **GENERATE**: Create data models and validation
3. **GENERATE**: Implement processing logic
4. **GENERATE**: Add monitoring and error handling
5. **VALIDATE**: Test with sample data
6. **CLEANUP**: Performance optimization

## Benefits

- **Cost Efficiency**: 93% reduction in API costs
- **Faster Execution**: Smaller context windows enable faster processing
- **Better Scalability**: Handles complex projects without context overflow
- **Maintained Quality**: Same code quality with dramatically lower token usage
- **Clear Traceability**: Step-by-step execution provides clear audit trail

## Implementation Details

### Plan Generation

The agent first analyzes requirements and generates a structured execution plan:

```
PLAN: User Management System
DESCRIPTION: Complete user authentication and management system

STEP: analyze_requirements
TYPE: analyze
GOAL: Understand project structure and requirements
...

STEP: create_user_model
TYPE: generate
DEPENDENCIES: analyze_requirements
GOAL: Create user data model
...
```

### Step Execution

Each step executes with minimal context:
- Step goal and description
- Relevant files only (not entire project)
- Artifacts from dependency steps only
- No full chat history

### Artifact Management

Steps produce focused artifacts that flow to dependent steps:
- Code blocks
- File paths
- Configuration data
- Validation results

## Performance Comparison

| Approach | Token Usage | Cost | Execution Time | Scalability |
|----------|-------------|------|----------------|-------------|
| Traditional | ~56k tokens | High | Slower | Limited |
| Step-Based | ~4k tokens | Low | Faster | Excellent |

## Configuration

The agent uses the same tool set as other StreetRace agents:
- File system operations
- CLI command execution
- MCP protocol tools
- Code analysis and generation

## Error Handling

- Individual step failures don't abort entire execution
- Dependency tracking prevents cascade failures
- Clear error reporting with step-level granularity
- Rollback capabilities for failed plans

## Future Enhancements

- Parallel step execution for independent steps
- Dynamic plan adjustment based on execution results
- Advanced artifact caching and reuse
- Integration with CI/CD pipelines
- Real-time collaboration features