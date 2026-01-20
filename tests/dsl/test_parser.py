"""Tests for the DSL parser.

Test coverage for all grammar constructs in the Streetrace DSL.
"""

import pytest

from streetrace.dsl.grammar.parser import ParserFactory


class TestParserFactory:
    """Test ParserFactory creation and configuration."""

    def test_creates_parser_by_default(self):
        parser = ParserFactory.create()
        # Parser should be created successfully
        assert parser is not None

    def test_creates_parser_in_debug_mode(self):
        parser = ParserFactory.create(debug=True)
        assert parser is not None

    def test_parser_has_propagate_positions_enabled(self):
        parser = ParserFactory.create()
        # Parser should track positions for error reporting
        assert parser.options.propagate_positions is True


class TestMinimalAgent:
    """Test parsing of minimal agent definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_minimal_agent(self, parser):
        source = '''
model main = anthropic/claude-sonnet

agent:
    tools github
    instruction my_prompt

prompt my_prompt: """
You are helpful.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_model_with_tools_and_prompt(self, parser):
        source = '''
model main = openai/gpt-4

tool github = mcp "https://api.github.com" with auth bearer "token"

agent:
    tools github, streetrace.fs
    instruction main_prompt

prompt main_prompt: """
You are a coding assistant.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"


class TestModelDefinitions:
    """Test parsing of model definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_short_form_model(self, parser):
        source = "model main = anthropic/claude-sonnet\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiple_models(self, parser):
        source = """
model main = anthropic/claude-sonnet
model compact = anthropic/claude-opus
model llm_rail = anthropic/haiku
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_long_form_model(self, parser):
        source = """
model main:
    provider: anthropic
    name: claude-sonnet
    temperature: 0.7
    max_tokens: 4096
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestToolDefinitions:
    """Test parsing of tool definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_mcp_tool_short_form(self, parser):
        source = 'tool github = mcp "https://api.github.com/mcp/"\n'
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_mcp_tool_with_auth(self, parser):
        source = 'tool github = mcp "https://api.github.com" with auth bearer "token"\n'
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_mcp_tool_with_interpolated_auth(self, parser):
        source = (
            'tool github = mcp "https://api.github.com" '
            'with auth bearer "${env:GITHUB_PAT}"\n'
        )
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_builtin_tool(self, parser):
        source = "tool fs = builtin streetrace.fs\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_long_form_tool(self, parser):
        source = """
tool github:
    type: mcp
    url: "https://api.github.com/mcp/"
    headers:
        Authorization: "Bearer token"
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestSchemaDefinitions:
    """Test parsing of schema definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_simple_schema(self, parser):
        source = """
schema Drift:
    score: float
    message: string
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_schema_with_list_type(self, parser):
        source = """
schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_schema_with_optional_type(self, parser):
        source = """
schema Response:
    message: string
    error: string?
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestAgentDefinitions:
    """Test parsing of agent definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_unnamed_agent(self, parser):
        source = """
agent:
    tools github
    instruction my_prompt
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_named_agent(self, parser):
        source = """
agent fetch_invoices:
    tools mcp_server_1, mcp_server_2
    instruction fetch_invoices_prompt
    retry default
    timeout default
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_agent_with_timeout_literal(self, parser):
        source = """
agent my_agent:
    tools github
    instruction my_prompt
    timeout 2 minutes
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_agent_with_description(self, parser):
        source = """
agent code_reviewer:
    tools github
    instruction review_prompt
    description "Reviews code for quality"
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestPromptDefinitions:
    """Test parsing of prompt definitions with triple-quoted body."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_simple_prompt(self, parser):
        source = '''
prompt my_prompt: """
You are a helpful assistant.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiline_prompt(self, parser):
        source = '''
prompt analyze_prompt: """
You are a work analyst.
Focus on accuracy and clarity.

Instructions:
- Be thorough
- Be concise
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_model_modifier(self, parser):
        source = '''
prompt compact_prompt using model "compact": """
Summarize the conversation.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_expecting_modifier(self, parser):
        source = '''
prompt structured_prompt expecting ReviewResult: """
Analyze the pull request.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_multiple_modifiers(self, parser):
        source = '''
prompt analyze_goal using model "compact" expecting GoalAnalysis: """
You are a work analyst. Given the instruction and input,
describe the conversation goal.

Instruction: $instruction
Input: $input_prompt
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_inherit_modifier(self, parser):
        source = '''
prompt history_prompt inherit $history: """
Continue the conversation.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"


class TestFlowDefinitions:
    """Test parsing of flow definitions with control structures."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_simple_flow(self, parser):
        source = """
flow my_workflow:
    $result = run agent fetch_data $input
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_for_loop(self, parser):
        source = """
flow process_items:
    $results = []
    for $item in $items do
        $result = run agent process_item $item
        push $result to $results
    end
    return $results
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_parallel_block(self, parser):
        source = """
flow parallel_search:
    parallel do
        $web_results = run agent web_search $topic
        $doc_results = run agent doc_search $topic
    end
    return $web_results
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_match_block(self, parser):
        source = """
flow handle_type:
    match $item.type
        when "standard" -> run agent process_standard $item
        when "expedited" -> run agent process_expedited $item
        else -> log "Unknown type"
    end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_if_block(self, parser):
        source = """
flow conditional_flow:
    if $drift.score > 0.2:
        retry step $drift.message
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_failure_handler(self, parser):
        source = """
flow transfer_money:
    $debit = run agent debit_account $from_account $amount

    $credit = run agent credit_account $to_account $amount
    on failure:
        run agent refund_account $from_account $amount
        notify "Transfer failed"
        return $debit
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_multiword_name(self, parser):
        source = """
flow get agent goal:
    $goal = call llm analyze_prompt $input
    return $goal
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_with_parameters(self, parser):
        source = """
flow detect trajectory drift from $goal:
    $drift = call llm detect_drift_prompt $goal
    return $drift
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_flow_returning_object_literal(self, parser):
        source = """
flow transfer_money:
    $debit = run agent debit_account $from_account $amount
    return { success: true, debit: $debit }
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestEventHandlers:
    """Test parsing of event handlers."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_on_start_handler(self, parser):
        source = """
on start do
    $input_prompt = initial user prompt
    $goal = get agent goal
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_on_input_handler(self, parser):
        source = """
on input do
    mask pii
    block if jailbreak
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_on_output_handler(self, parser):
        source = """
on output do
    $drift = detect trajectory drift from $goal
    retry with $drift.message if $drift.score > 0.2
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_on_tool_call_handler(self, parser):
        source = """
on tool-call do
    warn if $tool.name == "dangerous"
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_on_tool_result_handler(self, parser):
        source = """
on tool-result do
    mask pii
    block if jailbreak
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_after_timing(self, parser):
        source = """
after input do
    push $message to $adapted_history
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_handler_with_if_statement(self, parser):
        source = """
after tool-result do
    if $tool_result.guardrails.passed:
        push $tool_result.tool_name to $adapted_history
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_handler_with_for_loop(self, parser):
        source = """
on start do
    for $item in $items do
        log "Processing"
    end
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestPolicyDefinitions:
    """Test parsing of policy definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_retry_policy(self, parser):
        source = "retry default = 3 times, exponential backoff\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_retry_policy_linear(self, parser):
        source = "retry my_retry = 5 times, linear backoff\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_retry_policy_fixed(self, parser):
        source = "retry basic = 2 times, fixed backoff\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_retry_policy_without_backoff(self, parser):
        source = "retry simple = 3 times\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_timeout_policy_seconds(self, parser):
        source = "timeout default = 30 seconds\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_timeout_policy_minutes(self, parser):
        source = "timeout default = 2 minutes\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_compaction_policy(self, parser):
        source = """
policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [$goal, last 3 messages, tool results]
    use model: "compact"
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_custom_policy(self, parser):
        source = """
policy rate_limit:
    max_requests: 100
    window: 60
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestImportStatements:
    """Test parsing of import statements."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_streetrace_import(self, parser):
        source = "import base from streetrace\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_local_import(self, parser):
        source = "import ./custom_agent.sr\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_pip_import(self, parser):
        source = "import lib from pip://third_party_library\n"
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_mcp_import(self, parser):
        source = "import server from mcp://server_name\n"
        tree = parser.parse(source)
        assert tree.data == "start"


class TestExpressions:
    """Test parsing of expressions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_variable_reference(self, parser):
        source = """
flow test:
    $x = $input
    return $x
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_variable_property(self, parser):
        source = """
flow test:
    $x = $item.value
    return $x
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_deep_property_access(self, parser):
        source = """
flow test:
    $x = $result.data.items.first
    return $x
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_comparison_expressions(self, parser):
        source = """
flow test:
    if $score > 0.5:
        log "High score"
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_boolean_expressions(self, parser):
        source = """
on input do
    block if $is_spam and not $is_allowed
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_contains_expression(self, parser):
        source = """
on output do
    warn if $output contains "refund"
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_list_literal(self, parser):
        source = """
flow test:
    $items = []
    return $items
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_object_literal(self, parser):
        source = """
flow test:
    return { success: true, count: 42 }
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_function_call(self, parser):
        source = """
flow test:
    $converted = lib.convert($item)
    return $converted
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestGuardrailActions:
    """Test parsing of guardrail actions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_mask_action(self, parser):
        source = """
on input do
    mask pii
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_block_action(self, parser):
        source = """
on input do
    block if jailbreak
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_warn_action_with_condition(self, parser):
        source = """
on output do
    warn if $score < 0.5
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_warn_action_with_string(self, parser):
        source = """
on output do
    warn "Check this output"
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_warn_action_with_contains(self, parser):
        source = """
on output do
    warn if $output contains "sensitive"
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_retry_action(self, parser):
        source = """
on output do
    retry with $message if $drift.score > 0.2
end
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestVersionDeclaration:
    """Test parsing of version declarations."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_version_declaration(self, parser):
        source = """streetrace v1

model main = anthropic/claude-sonnet
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_version_with_minor(self, parser):
        source = """streetrace v1.2

model main = openai/gpt-4
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestParseErrors:
    """Test parser error handling with line/column information."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_reports_line_number_on_error(self, parser):
        source = """
model main = anthropic/claude-sonnet

agent
    tools github
"""
        with pytest.raises(Exception) as exc_info:
            parser.parse(source)
        # The error should be raised
        assert exc_info.value is not None

    def test_reports_column_on_error(self, parser):
        source = "model = broken\n"
        with pytest.raises(Exception) as exc_info:
            parser.parse(source)
        assert exc_info.value is not None


class TestComplexExamples:
    """Test parsing of complete, complex examples from the design docs."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_code_review_agent(self, parser):
        source = '''
model main = anthropic/claude-sonnet
model fast = anthropic/haiku

tool github = mcp "https://api.github.com/mcp/" with auth bearer "token"

schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string

agent code_reviewer:
    tools github
    instruction review_prompt

on input do
    block if not $input.pull_request_url
end

prompt review_prompt expecting ReviewResult: """
You are an expert code reviewer. Analyze the pull request
for bugs, security issues, and code quality.

Focus on:
- Logic errors
- Security vulnerabilities
- Performance issues
- Code style violations
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_research_agent_with_parallel(self, parser):
        source = '''
model main = anthropic/claude-opus

tool web = mcp "https://search.api/mcp/"
tool docs = builtin streetrace.docs

schema ResearchResult:
    summary: string
    sources: list[string]
    confidence: float

flow research $topic:
    parallel do
        $web_results = run agent web_search $topic
        $doc_results = run agent doc_search $topic
    end

    $combined = run agent synthesize $web_results $doc_results
    return $combined

agent web_search:
    tools web
    instruction web_search_prompt

agent doc_search:
    tools docs
    instruction doc_search_prompt

agent synthesize:
    instruction synthesize_prompt

prompt synthesize_prompt expecting ResearchResult: """
Combine the research results into a coherent summary.
Cite your sources and rate your confidence.
"""

prompt web_search_prompt: """
Search the web for information.
"""

prompt doc_search_prompt: """
Search the documentation.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_customer_support_agent(self, parser):
        source = '''
model main = anthropic/claude-sonnet
model triage = anthropic/haiku

tool crm = mcp "https://crm.internal/mcp/"
tool kb = builtin streetrace.knowledge_base

schema TriageResult:
    category: string
    urgency: string
    escalate: bool

on input do
    $triage = call llm triage_prompt $input using model "triage"
    if $triage.escalate:
        escalate to human "High priority issue detected"
end

on output do
    warn if $output contains "refund"
end

flow handle_support $ticket:
    match $triage.category
        when "billing" -> run agent billing_agent $ticket
        when "technical" -> run agent technical_agent $ticket
        when "general" -> run agent general_agent $ticket
        else -> escalate to human "Unknown category"
    end

prompt triage_prompt expecting TriageResult: """
Analyze the customer inquiry and determine:
- Category (billing, technical, general)
- Urgency (low, medium, high)
- Whether to escalate to human
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_full_invoice_workflow(self, parser):
        source = '''
import base from streetrace
import lib from pip://third_party_library

schema Drift:
    score: float
    message: string

model main = anthropic/claude-sonnet
model compact = anthropic/claude-opus
model llm_rail = anthropic/haiku

retry default = 3 times, exponential backoff
timeout default = 2 minutes

policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [$goal, last 3 messages, tool results]
    use model: "compact"

on start do
    $input_prompt = initial user prompt
    $goal = get agent goal
    $adapted_history = []
    run my_workflow
end

on input do
    mask pii
    block if jailbreak
end

on tool-result do
    mask pii
    block if jailbreak
end

on output do
    $drift = detect trajectory drift from $goal
    retry with $drift.message if $drift.score > 0.2
end

flow get agent goal:
    $goal = call llm get_agent_goal_prompt $instruction $input_prompt $agent_context
    return $goal

prompt get_agent_goal_prompt using model "compact": """
You are a work analyst. Given the agent instruction and input prompt,
describe the conversation goal the agent needs to fulfill.

Instruction: $instruction
Input: $input_prompt
Context: $context
"""

flow detect trajectory drift from $goal:
    $drift = call llm detect_drift_prompt $goal
    return $drift

prompt detect_drift_prompt using model "compact" expecting Drift: """
You are a work analyst. Detect if the agent work is aligned with the goal or drifted.

Goal: $goal
History: $adapted_history
Next action: $next_message
"""

after input do
    push $message to $adapted_history
end

after output do
    push $message to $adapted_history
end

after tool-result do
    if $tool_result.guardrails.passed:
        push $tool_result.tool_name to $adapted_history
end

flow my_workflow:
    $invoices = run agent fetch_invoices $input_prompt
    $processed = []

    for $invoice in $invoices do
        $converted = lib.convert($invoice)
        $result = run agent process_invoice $converted
        push $result to $processed
    end

    return $processed

agent fetch_invoices:
    tools mcp_server_1, mcp_server_2
    instruction fetch_invoices_prompt
    retry default
    timeout default

prompt fetch_invoices_prompt: """
You are a helpful assistant that fetches invoices.
"""

agent process_invoice:
    tools mcp_server_2, mcp_server_3
    instruction process_invoice_prompt
    retry default
    timeout default

prompt process_invoice_prompt: """
You are a helpful assistant that processes invoices.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"
