# Guardrails

## Overview

Guardrails are defense-in-depth security controls that intercept data flowing through your workflow. They can mask sensitive content, block dangerous inputs, warn on suspicious patterns, or retry with corrective instructions.

Nothing runs unless the DSL says so -- guardrails are composable library components, not platform infrastructure. You declare which guardrails apply to which events, and StreetRace wires them into the agent lifecycle automatically.

## Installation

PII masking requires Microsoft Presidio:

```bash
pip install 'streetrace[guardrails]'
```

Advanced guardrails (Prompt Proxy Stages 2/3, MCP-Guard neural inspector, Cognitive Monitor embeddings) require ONNX Runtime:

```bash
pip install onnxruntime
```

Jailbreak detection (Stage 1) and custom guardrails work without additional dependencies.

## Quick Start

### Scenario 1: Protect User Input

Mask personally identifiable information and block jailbreak attempts before they reach the model.

```streetrace
on input do
    mask pii
    block if jailbreak
end
```

### Scenario 2: Sanitize Model Output

Prevent the model from leaking PII in its responses.

```streetrace
on output do
    mask pii
end
```

### Scenario 3: Full Defense-in-Depth

Combine input protection, output sanitization, tool call validation, tool result scanning, and cognitive drift monitoring for comprehensive coverage.

Tool results deserve their own handler because they are **untrusted model input** -- the content comes from external tool servers, not the user or the model. A compromised or malicious MCP server can inject prompt overrides, PII, or encoded payloads in its response. The `on input` handler does not cover tool results; each event handler is independent.

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
    block if mcp_guard
end

on tool-result do
    mask pii
    block if jailbreak
end

after output do
    warn if cognitive_drift
end

agent:
    tools streetrace.fs
    instruction main_prompt

prompt main_prompt:
    You are a helpful coding assistant.
```

## Event Handlers

Guardrails execute inside event handlers. Each handler targets a specific point in the agent lifecycle and runs the guardrail actions you declare inside it.

### Supported Events

| Event | When it fires |
|-------|--------------|
| `input` | User message received |
| `output` | Model response generated |
| `tool-call` | Before tool execution |
| `tool-result` | After tool returns |

Each event has `on` (before processing) and `after` (after processing) variants.

### DSL Syntax

```streetrace
on <event> do
    <guardrail actions>
end

after <event> do
    <guardrail actions>
end
```

### Event Lifecycle

The table below shows how DSL event handlers map to ADK callbacks and the event phase recorded in OTEL spans:

| DSL Handler | ADK Callback | Event Phase |
|-------------|-------------|-------------|
| `on input` | `on_user_message_callback` | `input` |
| `after input` | `before_model_callback` | `input` |
| `on output` / `after output` | `after_model_callback` | `output` |
| `on tool-call` / `after tool-call` | `before_tool_callback` | `tool_call` |
| `on tool-result` / `after tool-result` | `after_tool_callback` | `tool_result` |

## Guardrail Actions

| Action | Description |
|--------|-------------|
| `mask <name>` | Replace sensitive content with placeholders |
| `block if <name>` | Block if guardrail triggers (raise `BlockedInputError`) |
| `warn if <condition>` | Log warning and continue processing |
| `warn "<message>"` | Log a specific warning message |
| `warn if <expression> contains "<pattern>"` | Conditional pattern warning |
| `retry with <message> if <condition>` | Re-prompt with correction if condition met |
| `retry step <expression>` | Retry a specific workflow step |

### Block Behavior by Context

What happens when `block` fires depends on the event context:

| Context | Behavior |
|---------|----------|
| `on input` | Return rejection message to user, abort workflow |
| `on tool-call` | Return error to model, model continues with other tools |
| `on tool-result` | Show blocked content message to model |
| `on output` | Replace output with redaction message |

## Built-in Guardrails

### PII Masking (`pii`)

**DSL name:** `pii`

**Action:** Mask-only (check always returns not triggered)

**Implementation:** Microsoft Presidio with spaCy `en_core_web_lg` model. Presidio's analyzer engine scans text for PII entities, and the anonymizer engine replaces each match with a type-specific placeholder.

**Detected entities:** `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `PERSON`, `LOCATION`, `ORGANIZATION`, and 30+ additional entity types from Presidio's recognizer registry.

**Output format:** Each entity is replaced with a placeholder like `[MASKED_EMAIL_ADDRESS]`, `[MASKED_PHONE_NUMBER]`, `[MASKED_PERSON]`, etc.

**Dependencies:** `pip install 'streetrace[guardrails]'` -- auto-installs Presidio + spaCy at first use if missing.

**Tool result handling:** For tool results, masks inspectable fields: `output`, `stdout`, `error`, `stderr`.

**Threats addressed:**
- Data leakage
- PII exposure in logs, traces, and model context
- Privacy compliance violations

**Usage:**

```streetrace
on input do
    mask pii
end

on output do
    mask pii
end
```

**Reference:** [Microsoft Presidio documentation](https://microsoft.github.io/presidio/)

---

### Jailbreak Detection / Prompt Proxy (`jailbreak`)

**DSL name:** `jailbreak`

**Action:** Check-only (mask returns text unchanged)

**Implementation:** 3-stage Prompt Proxy pipeline:

- **Stage 1 -- Syntactic Filter:** Regex pattern matching across 5 attack categories. Always available, no dependencies. Deterministic, confidence = 1.0.
- **Stage 2 -- Semantic Detector:** Cosine similarity against canonical injection embeddings using ONNX neural models. Requires `onnxruntime`.
- **Stage 3 -- Content Safety Classifier:** Neural content classification with configurable block threshold (default 0.80). Requires `onnxruntime`.

**Attack categories detected by Stage 1:**

- **Instruction Override:** "ignore previous instructions", DAN jailbreak, "pretend no restrictions", "reveal system prompt", "bypass safety", "ignore ethics/guidelines", "new instructions:"
- **Shell Injection:** `rm -rf`, `curl | sh`, backtick execution, `$()` command substitution
- **SQL Injection:** UNION SELECT, OR tautology, DROP TABLE, SQL comment terminators
- **Path Traversal:** `../../` sequences, `/etc/passwd`, `.env` files, `.ssh/` directories
- **Encoding Attacks:** Base64 payloads, hex escape sequences, unicode escape sequences

Stages 2 and 3 escalate when Stage 1 passes -- they catch semantically similar attacks that evade syntactic patterns.

**Configuration:** `PromptProxyConfig(enabled=True, warn_threshold=0.60, block_threshold=0.85)`

**Threats addressed:**
- Prompt injection
- System prompt extraction
- Jailbreaking
- Indirect injection via encoded payloads

**Usage:**

```streetrace
on input do
    block if jailbreak
end
```

**Research references:**
- [OWASP LLM Top 10 -- LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173) (Greshake et al., 2023)
- [Ignore This Title and HackAPrompt: Exposing Systemic Weaknesses of LLMs](https://arxiv.org/abs/2311.16119) (Schulhoff et al., 2023)

---

### MCP-Guard (`mcp_guard`)

**DSL name:** `mcp_guard`

**Action:** Check-only (mask returns text unchanged)

**Implementation:** Multi-stage MCP tool call validation:

- **Stage 0 -- Policy Enforcer:** Allowlist/denylist per server, rate limiting, data boundary patterns.
- **Stage 1 -- Syntactic Gatekeeper:** 6 parallel pattern detectors against tool names and arguments.
- **Stage 2 -- Neural Inspector:** Embedding-based structural anomaly detection (async-only, requires ONNX).

Plus **Trust Evaluator:** Per-server trust scores with manifest hash rug-pull detection.

**The 6 syntactic detectors:**

- **Shell Injection:** `rm -rf`, `curl|sh`, `eval $(`, backtick execution, `wget|sh`, `chmod +x`
- **SQL Injection:** UNION SELECT, OR tautology, DROP TABLE, SQL comment terminators
- **Sensitive File Access:** `/etc/passwd`, `.env`, `.ssh/`, `.git/`, `.aws/credentials`, `.docker/config.json`, `.kube/config`
- **Shadow Hijack:** Spoofed tool calls, fake server references, instruction override/tampering
- **Important Tag Abuse:** `<important>`, `<system>`, `<priority>` tag injection in tool arguments
- **Cross-Origin:** Cloud metadata endpoint (169.254.169.254), localhost/127.0.0.1, internal IP ranges (10.x, 172.16-31.x, 192.168.x)

**Configuration:** `McpGuardConfig(enabled=True, trust_threshold=0.5, server_allowlist=[], server_denylist=[])`

**Threats addressed:**
- Tool poisoning
- Rug-pull attacks
- Data exfiltration via MCP tools
- SSRF through tool arguments
- Privilege escalation

**Best placement:** `on tool-call` handler.

**Usage:**

```streetrace
on tool-call do
    block if mcp_guard
end
```

**Research references:**
- [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173) (Greshake et al., 2023)
- [Securing Agentic AI Systems](https://www.anthropic.com/research/securing-agentic-ai) (Anthropic, 2025)
- [MCP Specification](https://modelcontextprotocol.io/specification)

---

### Cognitive Drift Monitor (`cognitive_drift`)

**DSL name:** `cognitive_drift`

**Action:** Check-only (mask returns text unchanged)

**Implementation:** Multi-turn conversation analysis combining 5 components:

- **Turn Embedder:** Generate embeddings per conversation turn (ONNX or fallback hash-based).
- **Intent Tracker:** Two-tier risk scoring -- cosine delta baseline + optional GRU forward pass. Persists state across turns via ADK session.
- **Drift Detector:** Threshold comparison with configurable `min_turns_before_alert` to avoid false positives early in conversations.
- **Sequence Anomaly Detector:** Detect suspicious tool-use sequences that individually appear benign but collectively suggest adversarial intent. Default patterns: `data_exfiltration` (read_file -> encode_* -> send_*), `privilege_escalation` (list_users -> modify_permissions -> *).
- **MTTR Calculator:** Measure Mean Time To Recovery after interventions (turns + wall-clock time).

**Session-aware:** Uses `GuardrailProvider.set_invocation_context()` to access per-session state from ADK.

**Configuration:** `CognitiveMonitorConfig(enabled=True, warn_threshold=0.60, block_threshold=0.85, min_turns_before_alert=3)`

**Threats addressed:**
- Goal hijacking across multi-turn conversations
- Gradual context poisoning
- Behavioral drift through extended interactions
- Adversarial multi-step tool-use sequences

**Best placement:** `after output` to analyze full conversation turns.

**Usage:**

```streetrace
after output do
    warn if cognitive_drift
end
```

**Research references:**
- Cognitive Drift in Multi-Turn Agent Conversations -- behavioral monitoring for extended AI interactions
- [Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training](https://arxiv.org/abs/2401.05566) (Hubinger et al., 2024)
- [Poisoning Language Models During Instruction Tuning](https://arxiv.org/abs/2305.00944) (Wan et al., 2023)

## Custom Guardrails

Custom guardrails are Python functions registered via `GuardrailProvider.register_custom(name, func)`. The function receives `GuardrailContent` (a `str`, `ToolResultContent`, or `ToolCallContent`) and returns:

- `str` for masking operations (the masked text)
- `bool` for check operations (`True` = triggered)

Both sync and async functions are supported. Custom guardrails override built-in guardrails with the same name. Confidence score is 0.0 for custom checks (vs 1.0 for built-in).

### Example: Block Restricted Terms

```python
from streetrace.dsl.runtime.guardrail_provider import GuardrailProvider

provider = GuardrailProvider()

RESTRICTED_TERMS = ["PROJECT_ALPHA", "internal-api-key", "staging.internal.corp"]

def check_restricted(content):
    """Block messages containing restricted company terms."""
    text = str(content)
    for term in RESTRICTED_TERMS:
        if term.lower() in text.lower():
            return True
    return False

provider.register_custom("restricted_terms", check_restricted)
```

Then use in DSL:

```streetrace
on input do
    block if restricted_terms
end

on output do
    block if restricted_terms
end
```

### Example: Mask API Keys

```python
import re

def mask_api_keys(content):
    """Replace API key patterns with placeholders."""
    text = str(content)
    return re.sub(
        r"(?:sk|pk|api)[_-][a-zA-Z0-9]{20,}",
        "[MASKED_API_KEY]",
        text,
    )

provider.register_custom("api_keys", mask_api_keys)
```

DSL:

```streetrace
on output do
    mask api_keys
end
```

### Example: Async External Content Filter

```python
import httpx

async def external_content_filter(content):
    """Check content against an external moderation API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://moderation.example.com/v1/check",
            json={"text": str(content)},
        )
        result = response.json()
        return result.get("flagged", False)

provider.register_custom("content_filter", external_content_filter)
```

## Observability

Guardrail operations emit OpenTelemetry spans with the following attributes:

| Attribute | Type | Example | Always? |
|-----------|------|---------|---------|
| `openinference.span.kind` | string | `"GUARDRAIL"` | yes |
| `streetrace.guardrail.name` | string | `"pii"`, `"jailbreak"` | yes |
| `streetrace.guardrail.action` | string | `"mask"` or `"check"` | yes |
| `streetrace.guardrail.event_phase` | string | `"input"`, `"output"` | yes |
| `streetrace.guardrail.triggered` | bool | `true` if content modified/blocked | yes |
| `streetrace.guardrail.check.confidence` | float | `1.0` (built-in), `0.0` (custom) | on check |
| `input.value` | string | Pre-masking message | opt-in |
| `output.value` | string | Post-masking message or check result | yes |

### Content Capture

By default, pre-masking input is **not** captured in spans to avoid leaking sensitive data into your trace backend. Enable it with:

```bash
export STREETRACE_CAPTURE_GUARDRAIL_CONTENT_IN_SPANS=true
```

Post-masking output (`output.value`) is always included since it contains the already-sanitized content.

### Trace Hierarchy

When OTEL is configured, guardrail spans appear as children of the ADK agent span:

```
agent.root
├── guardrail.mask.pii              (event_phase=input)
├── guardrail.check.jailbreak       (event_phase=input)
├── llm.call
├── guardrail.check.mcp_guard       (event_phase=tool_call)
├── guardrail.mask.pii              (event_phase=output)
└── guardrail.check.cognitive_drift  (event_phase=output)
```

Span kind is set to `GUARDRAIL` from the OpenInference semantic conventions, so trace backends that understand OpenInference will categorize these spans correctly.

### Violation Events

When a check guardrail triggers, a structured `guardrail.violation` span event is emitted with attributes in the `streetrace.guardrail.violation.*` namespace including: `id`, `severity`, `action`, `guardrail_name`, `detail`, `confidence`.

## Audit Trail

### Violation Event Types

- **`ViolationEvent`** -- Base event (severity, action, guardrail_name, detail, confidence).
- **`PromptViolation`** -- Adds `stage`, `pattern_matched`, `embedding_score`.
- **`ToolViolation`** -- Adds `server_id`, `tool_name`, `trust_score`.
- **`DriftViolation`** -- Adds `session_id`, `turn_number`, `risk_score`.
- **`RecoveryEvent`** -- Adds `recovery_turns`, `recovery_time_ms` (MTTR-A metrics).

### Enrichment

`EventEnricher` adds `agent_id`, `org_id`, and `run_id` to violation events before OTEL export, enabling downstream analytics to correlate violations with their execution context.

### Compliance Mapping

`ComplianceMapper` maps violations to EU AI Act articles:

| Article | Title |
|---------|-------|
| 9 | Risk Management System |
| 12 | Record-Keeping |
| 14 | Human Oversight |
| 62 | Serious Incident Reporting |

## See Also

- [Syntax Reference](syntax-reference.md) -- Complete DSL grammar reference
- [Getting Started](getting-started.md) -- Introduction to StreetRace DSL
