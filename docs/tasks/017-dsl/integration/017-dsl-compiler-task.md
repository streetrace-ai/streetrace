# Task Definition: DSL Compiler Runtime Integration

## Feature Information

| Field | Value |
|-------|-------|
| **Feature ID** | 017-dsl-compiler |
| **Feature Name** | DSL Compiler Runtime Integration |
| **Source Design Doc** | [017-dsl-compiler.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-compiler.md) |
| **Related Documents** | [017-dsl-grammar.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-grammar.md), [017-dsl-integration.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-integration.md), [017-dsl-examples.md](/home/data/repos/github.com/streetrace-ai/rfc/design/017-dsl-examples.md) |
| **Code Review** | [017-dsl-compiler-task-code-review.md](../017-dsl-compiler-task-code-review.md) |
| **Implementation TODO** | [017-dsl-compiler-todo.md](../017-dsl-compiler-todo.md) |
| **Branch** | `feature/017-streetrace-dsl-2` |

## Summary

Complete the DSL compiler runtime integration to enable DSL-defined agents to execute with full functionality. The current implementation has a working parser, AST, semantic analysis, and code generation pipeline, but the runtime integration is incomplete. Key gaps include:

1. **Agent Configuration Loading**: DSL-defined tools, instructions, and models aren't properly loaded into the agent
2. **Flow Execution**: Flows generate Python code but don't integrate with ADK for actual agent execution
3. **Runtime Context Methods**: Multiple placeholder methods in `WorkflowContext` need implementation
4. **Semantic Validation**: Some error codes (E0008, E0010) not triggered appropriately
5. **CLI Options**: `--no-comments` filtering needs improvement

## Implementation Requirements

### Phase 1: Agent Configuration Loading (Critical Path)

Fix the `DslAgentLoader` to properly load agent configuration from DSL:

1. **Tool Loading** (`dsl_agent_loader.py`)
   - Parse `_tools` dict and create proper tool references
   - Integrate with `ToolProvider` to resolve tool specs
   - Map DSL tool definitions to ADK tool format
   - Pass tools to `LlmAgent` constructor

2. **Instruction Resolution** (`dsl_agent_loader.py`)
   - Read `agent.instruction` directly from `_agents` dict
   - Look up instruction name in `_prompts` dict
   - Remove keyword-matching fallback logic
   - Evaluate prompt lambda with context

3. **Model Resolution** (`dsl_agent_loader.py`)
   - Store `prompt.model` in codegen for each prompt
   - Implement model resolution hierarchy:
     1. Model from prompt's `using model` clause
     2. Fallback to model named "main"
     3. CLI `--model` argument overrides everything

4. **Align generic.sr with generic.yml**
   - Update `agents/generic.sr` to include all tools from `generic.yml`

### Phase 2: Runtime Context Implementation

Implement placeholder methods in `WorkflowContext`:

1. **`run_agent()`** - Execute agent via ADK
2. **`call_llm()`** - Make direct LLM calls
3. **`mask_pii()`** - Implement PII masking
4. **`check_jailbreak()`** - Implement jailbreak detection
6. **`process()`** - Apply transformation pipeline
7. **`escalate_to_human()`** - Human escalation integration

### Phase 3: Flow Execution with ADK Integration

Integrate flow execution with ADK agents:

1. **Refactor `DslAgentWorkflow`**
   - Add `create_agent()` method for agent instantiation
   - Add `run_root_adk_agent()` method for execution
   - Generate async generators yielding ADK events

2. **Fix ExpressionVisitor**
   - Handle `Token` nodes properly
   - Remove or improve warning for unknown types

3. **Update FlowVisitor Code Generation**
   - Generate async for loops with yield
   - Handle variable capture from final responses
   - Detect and optimize sequential agent patterns

4. **Integrate Flows with Entry Point**
   - Wire flow execution to ADK Runner lifecycle
   - Pass `--prompt` argument to flow as initial input

### Phase 4: Semantic Validation Improvements

1. **E0010 for Missing Required Properties**
   - Trigger when agent lacks instruction
   - Add `missing_required_property` factory method

2. **E0008 for Indentation Errors**
   - Map Lark indentation exceptions to E0008
   - Provide helpful suggestions

### Phase 5: CLI Improvements

1. **Fix `--no-comments` Flag**
   - Track which lines are source comments during codegen
   - Filter only marked comment lines

### Phase 6: Known Limitations Resolution

1. **Comma-Separated Tool Lists** - Verify proper handling
2. **Flow Parameters and Variables** - Ensure proper scoping
3. **Compaction Policies** - Implement `strategy` and `preserve`

### Phase 7: Parser and Example Updates

1. **Update Example Files**
   - Fix `match.sr` (marked "simplified")
   - Update `flow.sr` to pass user prompt
   - Ensure all examples work correctly

### Phase 8: Documentation Updates

1. Remove resolved "Known Limitations" from user docs
2. Update example files documentation

## Success Criteria

### Acceptance Tests (from Code Review)

| ID | Test | Expected Result |
|----|------|-----------------|
| E1 | `agents/generic.sr` matches `agents/generic.yml` tools | Tools: fs, github mcp, context7 mcp |
| E2 | Run `streetrace --agent agents/generic.sr --prompt="describe this repo"` | Agent-defined tools are loaded |
| E3 | Run `streetrace --agent agents/generic.sr --prompt="describe this repo"` | Tools execute and return results |
| E4 | Run `streetrace --agent agents/examples/dsl/specific_model.sr` | Uses `anthropic/claude-sonnet-4-5` |
| E5 | Agent loads exact DSL config | No keyword guessing for instruction |
| E6 | Model resolution follows spec | Prompt model → "main" → CLI override |
| E7 | All placeholder comments implemented | No "not yet implemented" comments |
| E8 | `--no-comments` flag works | Removes only source comments |
| E9 | Agent without instruction | Triggers E0010 error |
| E10 | Indentation errors | Use E0008 error code |
| E11 | Run `streetrace --agent agents/examples/dsl/flow.sr` | Flows execute with ADK |
| E12 | Known limitations resolved | All documented limitations fixed |

### Test Coverage Targets

| Module | Target |
|--------|--------|
| `dsl_agent_loader.py` | 90%+ |
| `flows.py` (codegen) | 90%+ |
| `workflow.py` (runtime) | 90%+ |
| `analyzer.py` | 90%+ |
| `cli.py` | 80%+ |

## Dependencies on Existing Code

- `streetrace/agents/agent_manager.py` - Agent discovery and creation
- `streetrace/workflow/supervisor.py` - Workflow orchestration
- `streetrace/tools/tool_provider.py` - Tool resolution
- `streetrace/llm/lite_llm_client.py` - LLM calls
- `streetrace/ui/ui_bus.py` - Event dispatch

## Key File References

| Component | File |
|-----------|------|
| Agent Loader | `src/streetrace/agents/dsl_agent_loader.py` |
| Flow Code Gen | `src/streetrace/dsl/codegen/visitors/flows.py` |
| Expression Code Gen | `src/streetrace/dsl/codegen/visitors/expressions.py` |
| Workflow Base | `src/streetrace/dsl/runtime/workflow.py` |
| Context | `src/streetrace/dsl/runtime/context.py` |
| Semantic Analyzer | `src/streetrace/dsl/semantic/analyzer.py` |
| Error Codes | `src/streetrace/dsl/errors/codes.py` |
| CLI | `src/streetrace/dsl/cli.py` |
| Parser Factory | `src/streetrace/dsl/grammar/parser.py` |
| Generic DSL Agent | `agents/generic.sr` |
| Generic YAML Agent | `agents/generic.yml` |
| Flow Example | `agents/examples/dsl/flow.sr` |
