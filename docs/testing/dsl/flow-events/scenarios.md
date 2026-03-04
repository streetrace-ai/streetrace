# Flow Event Yielding Test Scenarios

Manual end-to-end test scenarios for validating the Flow Event Yielding feature. This document
focuses on verifying that DSL flows correctly yield events during execution.

## Feature Scope

The Flow Event Yielding feature introduces these behaviors to validate:

1. **ADK Event Yielding**: `run agent` statements yield all ADK events (tool calls, responses)
2. **FlowEvent Yielding**: `call llm` statements yield LlmCallEvent and LlmResponseEvent
3. **Event Propagation**: Events bubble up through nested flows to the Supervisor
4. **Result Capture**: Final responses are captured from both event types
5. **UI Rendering**: Events display correctly in the terminal

## Reference Documents

- `docs/tasks/017-dsl/flow-event-yielding/tasks.md`: Task definition, 2026-01-27
- `docs/tasks/017-dsl/flow-event-yielding/todo.md`: Implementation plan, 2026-01-27
- `docs/dev/dsl/flow-events/overview.md`: Architecture documentation

## Test Scenarios

---

### Scenario 1: Single Agent Flow Yields ADK Events

**Purpose**: Verify a flow with one `run agent` statement yields all ADK events.

**Preconditions**:
- Environment set up per [environment-setup.md](environment-setup.md)
- Debug logging enabled: `export STREETRACE_LOG_LEVEL=DEBUG`

**Input File**: `agents/single_agent_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    List the files in the current directory and describe what you find.
    Be very concise.

agent analyzer:
    tools fs
    instruction analyze

flow main:
    $result = run agent analyzer $input_prompt
    return $result
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/single_agent_flow.sr "List files" 2>&1 | tee output.log
   ```

2. Check for ADK events in output:
   ```bash
   grep -E "\[Function Call\]|\[Function Result\]" output.log
   ```

**Expected Output**:
```
[Function Call] list_files(...)
[Function Result] list_files: [...]
```

The agent's final response should also appear.

**Verification Criteria**:
- [ ] `[Function Call]` appears for tool invocations
- [ ] `[Function Result]` appears for tool results
- [ ] Agent's final response is displayed
- [ ] No errors in log output

---

### Scenario 2: Multi-Agent Flow Yields Interleaved Events

**Purpose**: Verify a flow with multiple `run agent` statements yields events from each agent.

**Input File**: `agents/multi_agent_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    List the files in the current directory.

prompt summarize:
    Summarize the following analysis in one sentence:
    ${analysis}

agent analyzer:
    tools fs
    instruction analyze

agent summarizer:
    instruction summarize

flow main:
    $analysis = run agent analyzer $input_prompt
    $summary = run agent summarizer $analysis
    return $summary
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/multi_agent_flow.sr "Analyze project" 2>&1 | tee output.log
   ```

2. Check event sequence:
   ```bash
   grep -E "\[Function|\[LLM|analyzer|summarizer" output.log
   ```

**Expected Output**:
- Events from analyzer agent (tool calls/results)
- Analyzer's response text
- Summarizer's response text
- Final summary as the result

**Verification Criteria**:
- [ ] Events appear from analyzer first
- [ ] Events from summarizer appear after analyzer completes
- [ ] Both agents produce visible output
- [ ] Final response is the summary

---

### Scenario 3: Call LLM Yields FlowEvents

**Purpose**: Verify `call llm` statements yield LlmCallEvent and LlmResponseEvent.

**Input File**: `agents/call_llm_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku

prompt greet:
    Say hello to the user in a friendly way.
    User message: ${input_prompt}

prompt farewell using model "fast":
    Say goodbye briefly.

flow main:
    $greeting = call llm greet
    $goodbye = call llm farewell
    return $goodbye
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/call_llm_flow.sr "Hi there!" 2>&1 | tee output.log
   ```

2. Check for LLM events:
   ```bash
   grep -E "\[LLM Call\]|\[LLM Response\]" output.log
   ```

**Expected Output**:
```
[LLM Call] greet (model: anthropic/claude-sonnet)
<greeting response in markdown>
[LLM Call] farewell (model: anthropic/claude-haiku)
<farewell response in markdown>
```

**Verification Criteria**:
- [ ] `[LLM Call] greet` appears with model name
- [ ] `[LLM Call] farewell` appears with different model
- [ ] Both LLM responses render as markdown
- [ ] Final response is the farewell message

---

### Scenario 4: Mixed Flow with Agents and LLM Calls

**Purpose**: Verify flows mixing `run agent` and `call llm` yield both event types.

**Input File**: `agents/mixed_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt analyze:
    Analyze the project structure briefly.

prompt quick_summary:
    Provide a one-line summary of: ${data}

agent researcher:
    tools fs
    instruction analyze

flow main:
    $data = run agent researcher $input_prompt
    $summary = call llm quick_summary
    return $summary
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/mixed_flow.sr "Analyze this project" 2>&1 | tee output.log
   ```

2. Check for both event types:
   ```bash
   grep -E "\[Function|\[LLM Call\]" output.log
   ```

**Expected Output**:
- `[Function Call]` events from researcher agent
- `[Function Result]` events from tool execution
- Agent's analysis text
- `[LLM Call] quick_summary` for the LLM call
- One-line summary as final response

**Verification Criteria**:
- [ ] ADK events appear first (from agent)
- [ ] LLM Call event appears after agent completes
- [ ] Final response is from the LLM call, not the agent

---

### Scenario 5: Nested Flow Event Propagation

**Purpose**: Verify events from nested `run flow` calls propagate correctly.

**Input File**: `agents/nested_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greet:
    Say hello briefly.

prompt process:
    Echo back: ${input_prompt}

flow inner:
    $result = call llm process
    return $result

flow main:
    $greeting = call llm greet
    run flow inner
    return $greeting
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/nested_flow.sr "Test message" 2>&1 | tee output.log
   ```

2. Check for events from both flows:
   ```bash
   grep -E "\[LLM Call\]" output.log
   ```

**Expected Output**:
```
[LLM Call] greet (model: anthropic/claude-sonnet)
<greeting>
[LLM Call] process (model: anthropic/claude-sonnet)
<echo>
```

**Verification Criteria**:
- [ ] `[LLM Call] greet` appears
- [ ] `[LLM Call] process` appears (from inner flow)
- [ ] Both responses render
- [ ] Final response is from outer flow (greeting)

---

### Scenario 6: Parallel Block Sequential Execution

**Purpose**: Verify parallel blocks execute sequentially with events from each operation.

**Input File**: `agents/parallel_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt task1:
    Say "Task 1 complete"

prompt task2:
    Say "Task 2 complete"

agent agent1:
    instruction task1

agent agent2:
    instruction task2

flow main:
    parallel do
        $r1 = run agent agent1
        $r2 = run agent agent2
    end
    return $r2
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/parallel_flow.sr "Go" 2>&1 | tee output.log
   ```

2. Check execution order:
   ```bash
   grep -E "Task [12] complete" output.log
   ```

**Expected Output**:
- "Task 1 complete" appears before "Task 2 complete"
- Both agents complete successfully

**Verification Criteria**:
- [ ] Events from agent1 appear first
- [ ] Events from agent2 appear after agent1 completes
- [ ] Both tasks complete
- [ ] Note in logs about sequential execution (with DEBUG level)

---

### Scenario 7: Result Capture via get_last_result

**Purpose**: Verify `ctx.get_last_result()` correctly captures operation results.

**Input File**: `agents/result_capture.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt compute:
    Return exactly: COMPUTED_VALUE_123

flow main:
    $result = call llm compute
    return $result
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/result_capture.sr "compute" 2>&1 | tee output.log
   ```

2. Check final response:
   ```bash
   grep "COMPUTED_VALUE_123" output.log
   ```

**Expected Output**:
The final response contains "COMPUTED_VALUE_123" or similar computed value.

**Verification Criteria**:
- [ ] LLM Call event appears
- [ ] LLM Response event contains the computed value
- [ ] Final response matches the computed value
- [ ] Result was correctly captured and returned

---

### Scenario 8: Error Handling During Event Yielding

**Purpose**: Verify errors during operations are handled gracefully.

**Input File**: `agents/error_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt missing:
    Reference undefined: ${undefined_var}

flow main:
    $result = call llm missing
    return $result
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/error_flow.sr "test" 2>&1 | tee output.log
   ```

2. Check for error handling:
   ```bash
   grep -iE "error|undefined|failed" output.log
   ```

**Expected Output**:
- Error message about undefined variable
- No crash or unhandled exception

**Verification Criteria**:
- [ ] Error is reported to user
- [ ] Application doesn't crash
- [ ] Error message is helpful

---

### Scenario 9: Agent Entry Point (No Flow)

**Purpose**: Verify agent-only DSL files also yield events correctly.

**Input File**: `agents/agent_only.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt helper:
    List files in the current directory. Be brief.

agent default:
    tools fs
    instruction helper
```

**Test Steps**:

1. Run the agent:
   ```bash
   poetry run streetrace agents/agent_only.sr "List files" 2>&1 | tee output.log
   ```

2. Check for events:
   ```bash
   grep -E "\[Function Call\]|\[Function Result\]" output.log
   ```

**Expected Output**:
- Tool call events appear
- Tool result events appear
- Agent's final response

**Verification Criteria**:
- [ ] Events yield even without a flow
- [ ] Agent executes correctly
- [ ] Final response is captured

---

### Scenario 10: Flow with Return Value Capture

**Purpose**: Verify flow return values work with async generators.

**Input File**: `agents/return_flow.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt step1:
    Say "Step 1"

prompt step2:
    Say "Step 2: ${prev}"

flow main:
    $s1 = call llm step1
    $s2 = call llm step2
    return $s2
```

**Test Steps**:

1. Run the flow:
   ```bash
   poetry run streetrace agents/return_flow.sr "Go" 2>&1 | tee output.log
   ```

2. Check result:
   ```bash
   grep -E "Step [12]" output.log
   ```

**Expected Output**:
- Both LLM calls execute
- Final response is from step2
- Step 2 references step 1's output

**Verification Criteria**:
- [ ] Both LLM Call events appear
- [ ] Variable passing works ($s1 available for step2)
- [ ] Return value is from the correct step

---

## Validation Checklist

Use this checklist to track test completion:

- [ ] Scenario 1: Single Agent Flow Yields ADK Events
- [ ] Scenario 2: Multi-Agent Flow Yields Interleaved Events
- [ ] Scenario 3: Call LLM Yields FlowEvents
- [ ] Scenario 4: Mixed Flow with Agents and LLM Calls
- [ ] Scenario 5: Nested Flow Event Propagation
- [ ] Scenario 6: Parallel Block Sequential Execution
- [ ] Scenario 7: Result Capture via get_last_result
- [ ] Scenario 8: Error Handling During Event Yielding
- [ ] Scenario 9: Agent Entry Point (No Flow)
- [ ] Scenario 10: Flow with Return Value Capture

## Debugging Tips

### Enable Debug Logging

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace agents/test.sr "Hello" 2>&1 | tee debug.log
```

### Check Event Types

Look for event type discriminators in debug output:

```bash
grep -E "type.*llm_call|type.*llm_response" debug.log
```

### Verify Generator Execution

Check that flow methods are executing as generators:

```bash
grep -E "async for.*event|yield.*event" debug.log
```

### Trace Event Flow

Enable tracing to see event propagation:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace agents/test.sr "Hello" 2>&1 | grep -E "yield|dispatch"
```

### Check Code Generation

Dump generated Python to verify async generator pattern:

```bash
poetry run streetrace dsl dump-python agents/test.sr
```

Look for:
- `AsyncGenerator[Event | FlowEvent, None]` return type
- `async for _event in ctx.run_agent(...): yield _event`
- `ctx.get_last_result()` for result capture

## See Also

- [Environment Setup](environment-setup.md) - Setting up the test environment
- [Workload Scenarios](../../workloads/scenarios.md) - General workload testing
- [Developer Documentation](../../../dev/dsl/flow-events/overview.md) - Architecture details
