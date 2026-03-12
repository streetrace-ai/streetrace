# Guardrails

Guardrails are defense-in-depth security controls that intercept data flowing through
your workflow. They can mask sensitive content, block dangerous inputs, warn on
suspicious patterns, or retry with corrective instructions.

## Installation

PII masking requires Presidio and a spaCy language model:

```bash
pip install 'streetrace[guardrails]'
```

Jailbreak detection and custom guardrails work without additional dependencies.

## DSL Grammar

Guardrails are defined inside event handlers using the `on`/`after` keywords:

```streetrace
on <event> do
    <guardrail actions>
end
```

### Events

| Event | When it fires |
|-------|--------------|
| `input` | User message received |
| `output` | Model response generated |
| `tool-call` | Before tool execution |
| `tool-result` | After tool returns |

Each event has `on` (before processing) and `after` (after processing) variants.

### Guardrail Actions

| Action | Description |
|--------|-------------|
| `mask pii` | Replace PII with `[PII]` placeholders (Presidio) |
| `mask <name>` | Apply a custom masking guardrail |
| `block if jailbreak` | Block if jailbreak pattern detected |
| `block if <name>` | Block if custom guardrail triggers |
| `warn if <condition>` | Log warning, continue processing |
| `warn "<message>"` | Log specific warning message |
| `retry with <message>` | Re-prompt with correction |
| `retry with <message> if <condition>` | Conditional retry |

## Built-in Guardrails

### PII Masking

Uses Microsoft Presidio with the `en_core_web_lg` spaCy model to detect and replace
personally identifiable information:

```streetrace
on input do
    mask pii
end
```

Detected entities (names, emails, phone numbers, etc.) are replaced with `[PII]`
placeholders before reaching the model.

### Jailbreak Detection

Uses regex patterns to detect common prompt injection attempts:

```streetrace
on input do
    block if jailbreak
end
```

Detected patterns include instructions to ignore previous prompts, assume alternate
identities, bypass safety measures, or reveal system prompts.

## Event Lifecycle

The table below shows how DSL event handlers map to ADK callbacks and the event phase
recorded in OTEL spans:

| DSL Handler | ADK Callback | Event Phase |
|-------------|-------------|-------------|
| `on input` | `on_user_message_callback` | `input` |
| `after input` | `before_model_callback` | `input` |
| `on output` / `after output` | `after_model_callback` | `output` |
| `on tool-call` / `after tool-call` | `before_tool_callback` | `tool_call` |
| `on tool-result` / `after tool-result` | `after_tool_callback` | `tool_result` |

## Block Behavior

What happens when `block` fires depends on the event context:

| Context | Behavior |
|---------|----------|
| `on input` | Return rejection message to user, abort workflow |
| `on tool-call` | Return error to model, model continues with other tools |
| `on tool-result` | Show blocked content message to model |
| `on output` | Replace output with redaction message |

## Observability

Guardrail operations emit OpenTelemetry spans with the following attributes:

| Attribute | Type | Example | Always? |
|-----------|------|---------|---------|
| `openinference.span.kind` | string | `"GUARDRAIL"` | yes |
| `streetrace.guardrail.name` | string | `"pii"`, `"jailbreak"` | yes |
| `streetrace.guardrail.action` | string | `"mask"` or `"check"` | yes |
| `streetrace.guardrail.event_phase` | string | `"input"`, `"output"` | yes |
| `streetrace.guardrail.triggered` | bool | `true` if content modified/blocked | yes |
| `input.value` | string | Pre-masking message | opt-in |
| `output.value` | string | Post-masking message or check result | yes |

### Content Capture

By default, pre-masking input is **not** captured in spans to avoid leaking sensitive
data into your trace backend. To enable it:

```bash
export STREETRACE_CAPTURE_GUARDRAIL_CONTENT_IN_SPANS=true
```

Post-masking output (`output.value`) is always included since it contains the
already-sanitized content.

### Trace Hierarchy

When OTEL is configured, guardrail spans appear as children of the ADK agent span:

```
agent.root
├── guardrail.mask.pii          (event_phase=input)
├── guardrail.check.jailbreak   (event_phase=input)
├── llm.call
├── guardrail.mask.pii          (event_phase=output)
└── guardrail.check.jailbreak   (event_phase=tool_call)
```

Span kind is set to `GUARDRAIL` from the OpenInference semantic conventions, so trace
backends that understand OpenInference will categorize these spans correctly.

## Examples

### Basic Input Protection

```streetrace
on input do
    mask pii
    block if jailbreak
end
```

### Output Masking

```streetrace
on output do
    mask pii
end

after output do
    push $message to $history
end
```

### Multi-handler Workflow

```streetrace
model main = anthropic/claude-sonnet

on input do
    mask pii
    block if jailbreak
end

on output do
    mask pii
end

on tool-call do
    warn if jailbreak
end

agent:
    tools streetrace.fs
    instruction main_prompt

prompt main_prompt:
    You are a helpful coding assistant.
```

## See Also

- [Syntax Reference](syntax-reference.md) - Complete DSL grammar reference
- [Getting Started](getting-started.md) - Introduction to Streetrace DSL
