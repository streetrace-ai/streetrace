"""Tests for DSL examples from design documentation.

Verify that all examples from the design documents parse correctly
and pass semantic validation where applicable.
"""

import pytest

from streetrace.dsl import validate_dsl
from streetrace.dsl.grammar import ParserFactory

# =============================================================================
# Examples from Design Document (017-dsl-examples.md)
# =============================================================================

# Section 1: Minimal Agent
MINIMAL_AGENT = """\
model main = anthropic/claude-sonnet

tool github = mcp "https://api.github.com/mcp/"

agent:
    tools github
    instruction my_prompt

prompt my_prompt: \"\"\"You are a helpful assistant.\"\"\"
"""

# Section 2.1: Model Definitions - Short Form
MODELS_SHORT_FORM = """\
model main = anthropic/claude-sonnet
model compact = anthropic/claude-opus
model llm_rail = anthropic/haiku
"""

# Section 2.1: Model Definitions - Long Form
MODEL_LONG_FORM = """\
model main:
    provider: anthropic
    name: claude-sonnet
    temperature: 0.7
    max_tokens: 4096
"""

# Section 2.2: Schemas
SCHEMA_EXAMPLE = """\
schema Drift:
    score: float
    message: string
"""

# Section 2.2: Schema with list type
SCHEMA_WITH_LIST = """\
schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string
"""

# Section 2.3: Tool Definitions - Short Form
TOOLS_SHORT_FORM = """\
tool github = mcp "https://api.github.com/mcp/"
tool fs = builtin streetrace.fs
"""

# Section 2.3: Tool Definitions - Long Form
TOOL_LONG_FORM = """\
tool github:
    type: mcp
    url: "https://api.github.com/mcp/"
    headers:
        Authorization: "Bearer token"
"""

# Section 2.5: Event Handlers
EVENT_HANDLERS = """\
model main = anthropic/claude-sonnet

on start do
    $initialized = true
end

on input do
    mask pii
end

on output do
    mask pii
end
"""

# Section 2.6: Simple Flow
SIMPLE_FLOW = """\
model main = anthropic/claude-sonnet

prompt my_prompt: \"\"\"Help with the task.\"\"\"

tool github = mcp "https://api.github.com/mcp/"

agent sub_agent:
    tools github
    instruction my_prompt

flow my_flow:
    $result = run agent sub_agent
    return $result
"""

# Section 2.7: Agent Definition
AGENT_DEFINITION = """\
model main = anthropic/claude-sonnet

prompt my_prompt: \"\"\"You are a helpful assistant.\"\"\"

tool github = mcp "https://api.github.com/mcp/"

agent my_agent:
    tools github
    instruction my_prompt
    timeout 2 minutes
"""

# Section 2.8: Prompt with Modifier
PROMPT_WITH_MODIFIER = """\
model compact = anthropic/claude-opus

prompt analyze_goal using model "compact": \"\"\"You are a work analyst.\"\"\"
"""

# Section 5: Guardrails
GUARDRAILS_EXAMPLE = """\
model main = anthropic/claude-sonnet

on input do
    mask pii
    block if jailbreak
end

on tool-result do
    mask pii
    block if jailbreak
end

on output do
    warn if sensitive
end
"""

# Section 6: Policies
POLICY_COMPACTION = """\
model main = anthropic/claude-sonnet

policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [last 3 messages, tool results]
"""

# Section 7: Retry and Timeout Policies
RELIABILITY_POLICIES = """\
model main = anthropic/claude-sonnet

retry default = 3 times, exponential backoff
timeout default = 2 minutes

prompt fetch_prompt: \"\"\"Fetch invoices.\"\"\"

tool invoice_api = mcp "https://invoice.api/mcp/"

agent fetch_invoices:
    tools invoice_api
    instruction fetch_prompt
    retry default
    timeout default
"""

# Section 10.1: Code Review Agent (simplified)
CODE_REVIEW_AGENT = """\
model main = anthropic/claude-sonnet
model fast = anthropic/haiku

tool github = mcp "https://api.github.com/mcp/"

schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string

agent code_reviewer:
    tools github
    instruction review_prompt

prompt review_prompt expecting ReviewResult: \"\"\"
You are an expert code reviewer. Analyze the pull request
for bugs, security issues, and code quality.
\"\"\"
"""

# Section 10.2: Research Agent with Parallel Search (simplified)
RESEARCH_AGENT = """\
model main = anthropic/claude-opus

tool web = mcp "https://search.api/mcp/"
tool docs = builtin streetrace.docs

prompt web_search_prompt: \"\"\"Search the web.\"\"\"
prompt doc_search_prompt: \"\"\"Search the docs.\"\"\"
prompt synthesize_prompt: \"\"\"Combine results.\"\"\"

agent web_search:
    tools web
    instruction web_search_prompt

agent doc_search:
    tools docs
    instruction doc_search_prompt

agent synthesize:
    instruction synthesize_prompt

flow research:
    parallel do
        $web_results = run agent web_search
        $doc_results = run agent doc_search
    end
    $combined = run agent synthesize with $web_results
    return $combined
"""


# =============================================================================
# Parsing Tests
# =============================================================================

PARSING_EXAMPLES = [
    ("minimal_agent", MINIMAL_AGENT),
    ("models_short_form", MODELS_SHORT_FORM),
    ("model_long_form", MODEL_LONG_FORM),
    ("schema_example", SCHEMA_EXAMPLE),
    ("schema_with_list", SCHEMA_WITH_LIST),
    ("tools_short_form", TOOLS_SHORT_FORM),
    ("tool_long_form", TOOL_LONG_FORM),
    ("event_handlers", EVENT_HANDLERS),
    ("simple_flow", SIMPLE_FLOW),
    ("agent_definition", AGENT_DEFINITION),
    ("prompt_with_modifier", PROMPT_WITH_MODIFIER),
    ("guardrails_example", GUARDRAILS_EXAMPLE),
    ("policy_compaction", POLICY_COMPACTION),
    ("reliability_policies", RELIABILITY_POLICIES),
    ("code_review_agent", CODE_REVIEW_AGENT),
    ("research_agent", RESEARCH_AGENT),
]


class TestExamplesParsing:
    """Test that all design doc examples parse correctly."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    @pytest.mark.parametrize(("name", "source"), PARSING_EXAMPLES)
    def test_example_parses(self, name: str, source: str, parser) -> None:  # noqa: ARG002
        """All design doc examples should parse without errors."""
        tree = parser.parse(source)
        assert tree is not None
        assert tree.data == "start"


# =============================================================================
# Validation Tests
# =============================================================================

# Examples that should pass full validation (semantic analysis)
VALIDATION_EXAMPLES = [
    ("minimal_agent", MINIMAL_AGENT),
    ("models_short_form", MODELS_SHORT_FORM),
    ("model_long_form", MODEL_LONG_FORM),
    ("schema_example", SCHEMA_EXAMPLE),
    ("schema_with_list", SCHEMA_WITH_LIST),
    ("tools_short_form", TOOLS_SHORT_FORM),
    ("tool_long_form", TOOL_LONG_FORM),
    ("event_handlers", EVENT_HANDLERS),
    ("simple_flow", SIMPLE_FLOW),
    ("agent_definition", AGENT_DEFINITION),
    ("guardrails_example", GUARDRAILS_EXAMPLE),
    ("reliability_policies", RELIABILITY_POLICIES),
    ("code_review_agent", CODE_REVIEW_AGENT),
]


class TestExamplesValidation:
    """Test that complete examples pass semantic validation."""

    @pytest.mark.parametrize(("name", "source"), VALIDATION_EXAMPLES)
    def test_example_validates(self, name: str, source: str) -> None:
        """Complete examples should pass semantic validation."""
        diagnostics = validate_dsl(source, f"{name}.sr")
        errors = [d for d in diagnostics if d.severity.name.lower() == "error"]

        assert not errors, (
            f"Example '{name}' has semantic errors: "
            f"{[e.message for e in errors]}"
        )
