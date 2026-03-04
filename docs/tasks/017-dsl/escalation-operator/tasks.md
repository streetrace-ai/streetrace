# Task Definition: Normalized Comparison Operator and Prompt Escalation

## Feature Information

- **Feature ID**: 017-dsl
- **Task ID**: escalation-operator
- **Branch**: feature/017-streetrace-dsl-2

## Design Documents

- **Primary Design**: `docs/tasks/017-dsl/escalation-operator/tasks.md` (this file)
- **Implementation Plan**: `docs/tasks/017-dsl/escalation-operator/todo.md`
- **Grammar Reference**: `src/streetrace/dsl/grammar/streetrace.lark`

## Summary

Implement two related features that enable cleaner agent communication patterns in the DSL:

1. **Normalized comparison operator (`~`)** - Case-insensitive, whitespace/punctuation-stripped equality
2. **Prompt-level escalation conditions** - Define when a prompt's output should trigger escalation
3. **Run statement escalation handlers** - Handle escalation at the call site

### Motivation

When agents communicate, LLM outputs often include formatting noise (markdown, punctuation,
whitespace). The current pattern requires verbose code:

```sr
# Current verbose pattern
$new = run agent peer1 $current
if $new == "DRIFTING":
    return $current
$current = $new
```

Problems:
- Extra variable (`$new`) just to check before assignment
- Comparison fails on `"**Drifting.**\n"` vs `"DRIFTING"`
- No separation between "when to escalate" (prompt logic) and "what to do" (flow logic)

### Solution

Inspired by [Google ADK's escalation pattern](https://google.github.io/adk-docs/agents/multi-agents/),
we separate escalation definition from escalation handling:

```sr
# Proposed clean pattern
prompt pi_enhancer using model "main": """..."""
    escalate if ~ "DRIFTING"

agent peer1:
    instruction pi_enhancer

flow default:
    $current = $input_prompt
    loop max 3 do
        $current = run agent peer1 $current, on escalate return $current
        $current = run agent peer2 $current, on escalate return $current
    end
    return $current
```

**Plain English**: "Run peer1. If it escalates (output matches ~DRIFTING), return current value."

## Feature Specifications

### 1. Normalized Comparison Operator (`~`)

The `~` operator performs "normalized equality" - comparing values after cleaning LLM formatting noise.

**Normalization rules**:
1. Convert to lowercase
2. Strip leading/trailing whitespace
3. Remove punctuation (`.`, `!`, `?`, `,`, `;`, `:`)
4. Remove markdown modifiers (`**`, `*`, `_`, `` ` ``, `#`)
5. Collapse multiple whitespace to single space

**Examples**:

| Left | Right | Result |
|------|-------|--------|
| `"DRIFTING"` | `"DRIFTING"` | `true` |
| `"drifting"` | `"DRIFTING"` | `true` |
| `"**Drifting.**\n"` | `"DRIFTING"` | `true` |
| `"  Drifting!  "` | `"DRIFTING"` | `true` |
| `"I am drifting"` | `"DRIFTING"` | `false` (not equal) |

**Grammar change** (line 398 of `streetrace.lark`):
```lark
comparison_op: ">" | "<" | ">=" | "<=" | "==" | "!=" | "contains" | "~"
```

**Usable anywhere expressions are valid**:
```sr
if $response ~ "YES":
    log "Confirmed"

$is_approved = $answer ~ "APPROVED"

match $status
    when ~ "SUCCESS" -> return { success: true }
end
```

### 2. Prompt Escalation Clause

Prompts can define conditions that trigger escalation based on output.

**Grammar addition**:
```lark
prompt_def: "prompt" NAME prompt_modifiers? ":" prompt_body escalation_clause?

escalation_clause: "escalate" "if" escalation_condition _NL

escalation_condition: "~" STRING           // normalized equals
                    | "==" STRING          // exact match
                    | "!=" STRING          // not equals
                    | "contains" STRING    // substring
                    | expression           // general boolean
```

**Examples**:
```sr
# Normalized match (recommended for LLM outputs)
prompt analyzer: """..."""
    escalate if ~ "ESCALATE"

# Exact match
prompt classifier: """..."""
    escalate if == "NEEDS_HUMAN"

# Contains check
prompt detector: """..."""
    escalate if contains "ERROR"
```

**Semantics**:
- Escalation condition is stored with the prompt definition
- When an agent using this prompt produces output matching the condition, the escalation flag is set
- The calling flow can then handle the escalation via `on escalate` clause

### 3. Run Statement Escalation Handler

Run statements can include an escalation handler that executes when the called agent escalates.

**Grammar addition**:
```lark
run_stmt: variable "=" "run" "agent" identifier expression* escalation_handler?
        | "run" "agent" identifier expression* escalation_handler?
        | variable "=" "run" identifier expression* escalation_handler?  -> run_flow_assign
        | "run" identifier expression* escalation_handler?  -> run_flow

escalation_handler: "," "on" "escalate" escalation_action

escalation_action: "return" expression
                 | "continue"
                 | "abort"
```

**Examples**:
```sr
# Return previous value on escalation
$current = run agent peer1 $current, on escalate return $current

# Continue loop iteration on escalation
run agent validator $data, on escalate continue

# Abort flow on escalation
$result = run agent processor $input, on escalate abort
```

**Semantics**:
- When the agent's output triggers its prompt's escalation condition, the handler executes
- `return $value` - immediately returns from the flow with the given value
- `continue` - skip remaining loop body, continue with next iteration
- `abort` - raise `AbortError` to stop execution

## AST Node Changes

### Modified: `PromptDef` (nodes.py:437)

```python
@dataclass
class PromptDef:
    """Prompt definition node."""

    name: str
    body: str
    model: str | None = None
    expecting: str | None = None
    inherit: str | None = None
    escalation_condition: EscalationCondition | None = None  # NEW
    meta: SourcePosition | None = None
```

### New: `EscalationCondition`

```python
@dataclass
class EscalationCondition:
    """Escalation condition for prompt outputs."""

    op: str  # "~", "==", "!=", "contains", or "expr"
    value: str | AstNode  # String literal or expression
    meta: SourcePosition | None = None
```

### Modified: `RunStmt` (nodes.py:133)

```python
@dataclass
class RunStmt:
    """Run statement node for agents and flows."""

    target: str | None
    agent: str
    args: list[AstNode]
    meta: SourcePosition | None = None
    is_flow: bool = False
    escalation_handler: EscalationHandler | None = None  # NEW
```

### New: `EscalationHandler`

```python
@dataclass
class EscalationHandler:
    """Handler for agent escalation."""

    action: str  # "return", "continue", "abort"
    value: AstNode | None = None  # For return action
    meta: SourcePosition | None = None
```

## Code Generation Changes

### 1. Expression Visitor (`visitors/expressions.py`)

Add `~` operator handling:

```python
# In OPERATOR_MAP or special handling
if op == "~":
    # Generate call to runtime normalization function
    return f"_normalized_equals({left}, {right})"
```

### 2. Flow Visitor (`visitors/flows.py`)

Update `_visit_run_stmt` to handle escalation:

```python
def _visit_run_stmt(self, node: RunStmt) -> None:
    # ... existing agent/flow call generation ...

    if node.escalation_handler:
        handler = node.escalation_handler
        # Wrap call in escalation check
        self._emitter.emit("if _escalated:")
        self._emitter.indent()
        if handler.action == "return":
            value = self._expr_visitor.visit(handler.value)
            self._emitter.emit(f"return {value}")
        elif handler.action == "continue":
            self._emitter.emit("continue")
        elif handler.action == "abort":
            self._emitter.emit("raise AbortError('Escalation triggered abort')")
        self._emitter.dedent()
```

### 3. Workflow Visitor (`visitors/workflow.py`)

Update prompt emission to include escalation conditions:

```python
def _emit_prompts(self) -> None:
    for prompt in self._prompts:
        # Emit prompt with escalation condition
        escalation = None
        if prompt.escalation_condition:
            cond = prompt.escalation_condition
            escalation = f"EscalationCondition('{cond.op}', '{cond.value}')"

        self._emitter.emit(
            f"'{prompt.name}': PromptSpec("
            f"body=lambda ctx: {body}, "
            f"escalation={escalation}),"
        )
```

## Runtime Changes

### 1. New: `_normalized_equals()` function (`runtime/utils.py`)

```python
import re
import string

def _normalized_equals(left: object, right: object) -> bool:
    """Perform normalized equality comparison."""
    return _normalize(str(left)) == _normalize(str(right))

def _normalize(text: str) -> str:
    """Normalize text for comparison."""
    # Remove markdown modifiers
    text = re.sub(r'[*_`#]+', '', text)
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Lowercase and strip
    text = text.lower().strip()
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text
```

### 2. Modified: `WorkflowContext.run_agent()` (`runtime/context.py`)

Track escalation state from agent execution:

```python
async def run_agent(
    self,
    agent_name: str,
    *args: object,
) -> tuple[object, bool]:  # Returns (result, escalated)
    """Run agent and check for escalation."""
    result = await self._workflow.run_agent(agent_name, *args)

    # Check escalation condition from agent's prompt
    escalated = self._check_escalation(agent_name, result)

    return result, escalated

def _check_escalation(self, agent_name: str, result: object) -> bool:
    """Check if result triggers escalation condition."""
    agent_def = self._agents.get(agent_name)
    if not agent_def:
        return False

    prompt_name = agent_def.get("instruction")
    prompt_spec = self._prompts.get(prompt_name)
    if not prompt_spec or not prompt_spec.escalation:
        return False

    cond = prompt_spec.escalation
    result_str = str(result)

    if cond.op == "~":
        return _normalized_equals(result_str, cond.value)
    elif cond.op == "==":
        return result_str == cond.value
    elif cond.op == "!=":
        return result_str != cond.value
    elif cond.op == "contains":
        return cond.value in result_str

    return False
```

### 3. New: `PromptSpec` dataclass (`runtime/workflow.py`)

```python
@dataclass
class PromptSpec:
    """Prompt specification with optional escalation."""

    body: Callable[[WorkflowContext], str]
    escalation: EscalationCondition | None = None
```

## Integration with Existing Code

### Comparison Operator Pipeline

The `~` operator flows through the existing expression pipeline:

1. **Grammar** (`streetrace.lark:398`): Add `"~"` to `comparison_op`
2. **Transformer** (`transformer.py:1943`): No change - returns operator string
3. **AST** (`nodes.py:70`): `BinaryOp.op` already accepts any string
4. **Codegen** (`expressions.py:152`): Add special handling for `~`
5. **Runtime**: New `_normalized_equals()` function

### Escalation Pipeline

Escalation is a new concept that integrates with existing prompt/agent execution:

1. **Grammar**: New `escalation_clause` rule on `prompt_def`
2. **Transformer**: New `escalation_clause()` method
3. **AST**: Modified `PromptDef`, new `EscalationCondition`
4. **Codegen**: Emit escalation conditions in prompt specs
5. **Runtime**: Check escalation in `run_agent()`, return flag

## Success Criteria

- [ ] `~` operator works in all expression contexts (if, match, assignment)
- [ ] `~` correctly normalizes markdown, punctuation, whitespace, case
- [ ] Prompts can define `escalate if` conditions
- [ ] Run statements can include `on escalate` handlers
- [ ] `on escalate return $value` returns immediately with value
- [ ] `on escalate continue` skips to next loop iteration
- [ ] `on escalate abort` raises AbortError
- [ ] All existing tests pass
- [ ] Example `resolver.sr` works with new syntax

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Grammar conflicts with `~` | Medium | Test parser extensively |
| Breaking existing prompts | Low | Escalation clause is optional |
| Performance of normalization | Low | Simple string operations, cache if needed |
| Semantic confusion | Medium | Clear documentation, intuitive naming |

## References

- [Google ADK Multi-Agent Escalation](https://google.github.io/adk-docs/agents/multi-agents/)
- [ADK LoopAgent Escalation Pattern](https://medium.com/google-developer-experts/build-ai-agents-that-self-correct-until-its-right-adk-loopagent-f620bf351462)
- [ADK Escalation Discussion](https://github.com/google/adk-python/discussions/3714)
