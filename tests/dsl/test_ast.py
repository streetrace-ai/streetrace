"""Tests for AST nodes and transformer.

Test coverage for AST node creation and parse tree to AST transformation.
"""

import pytest

from streetrace.dsl.grammar.parser import ParserFactory


class TestAstNodeCreation:
    """Test that AST nodes can be created with required fields."""

    def test_dsl_file_node_creation(self):
        from streetrace.dsl.ast.nodes import DslFile

        dsl_file = DslFile(
            version=None,
            statements=[],
        )
        assert dsl_file.version is None
        assert dsl_file.statements == []

    def test_version_decl_node_creation(self):
        from streetrace.dsl.ast.nodes import VersionDecl

        version = VersionDecl(version="v1.0")
        assert version.version == "v1.0"

    def test_import_stmt_node_creation(self):
        from streetrace.dsl.ast.nodes import ImportStmt

        import_stmt = ImportStmt(
            name="base",
            source="streetrace",
            source_type="streetrace",
        )
        assert import_stmt.name == "base"
        assert import_stmt.source == "streetrace"
        assert import_stmt.source_type == "streetrace"

    def test_model_def_short_form_creation(self):
        from streetrace.dsl.ast.nodes import ModelDef

        model = ModelDef(
            name="main",
            provider_model="anthropic/claude-sonnet",
            properties=None,
        )
        assert model.name == "main"
        assert model.provider_model == "anthropic/claude-sonnet"
        assert model.properties is None

    def test_model_def_long_form_creation(self):
        from streetrace.dsl.ast.nodes import ModelDef

        model = ModelDef(
            name="main",
            provider_model=None,
            properties={
                "provider": "anthropic",
                "name": "claude-sonnet",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        )
        assert model.name == "main"
        assert model.provider_model is None
        assert model.properties["provider"] == "anthropic"

    def test_schema_def_creation(self):
        from streetrace.dsl.ast.nodes import SchemaDef, SchemaField, TypeExpr

        field = SchemaField(
            name="score",
            type_expr=TypeExpr(base_type="float", is_list=False, is_optional=False),
        )
        schema = SchemaDef(name="Drift", fields=[field])
        assert schema.name == "Drift"
        assert len(schema.fields) == 1
        assert schema.fields[0].name == "score"

    def test_type_expr_list_type_creation(self):
        from streetrace.dsl.ast.nodes import TypeExpr

        type_expr = TypeExpr(
            base_type="string",
            is_list=True,
            is_optional=False,
        )
        assert type_expr.base_type == "string"
        assert type_expr.is_list is True
        assert type_expr.is_optional is False

    def test_type_expr_optional_type_creation(self):
        from streetrace.dsl.ast.nodes import TypeExpr

        type_expr = TypeExpr(
            base_type="string",
            is_list=False,
            is_optional=True,
        )
        assert type_expr.base_type == "string"
        assert type_expr.is_list is False
        assert type_expr.is_optional is True

    def test_tool_def_short_form_creation(self):
        from streetrace.dsl.ast.nodes import ToolDef

        tool = ToolDef(
            name="github",
            tool_type="mcp",
            url="https://api.github.com",
            auth_type="bearer",
            auth_value="token",
        )
        assert tool.name == "github"
        assert tool.tool_type == "mcp"
        assert tool.auth_type == "bearer"

    def test_tool_def_builtin_creation(self):
        from streetrace.dsl.ast.nodes import ToolDef

        tool = ToolDef(
            name="fs",
            tool_type="builtin",
            builtin_ref="streetrace.fs",
        )
        assert tool.name == "fs"
        assert tool.tool_type == "builtin"
        assert tool.builtin_ref == "streetrace.fs"

    def test_agent_def_creation(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name="fetch_invoices",
            tools=["mcp_server_1", "mcp_server_2"],
            instruction="fetch_invoices_prompt",
            retry="default",
            timeout_ref="default",
        )
        assert agent.name == "fetch_invoices"
        assert len(agent.tools) == 2
        assert agent.instruction == "fetch_invoices_prompt"

    def test_agent_def_unnamed_creation(self):
        from streetrace.dsl.ast.nodes import AgentDef

        agent = AgentDef(
            name=None,
            tools=["github"],
            instruction="my_prompt",
        )
        assert agent.name is None
        assert agent.tools == ["github"]

    def test_prompt_def_creation(self):
        from streetrace.dsl.ast.nodes import PromptDef

        prompt = PromptDef(
            name="my_prompt",
            body="You are a helpful assistant.",
            model=None,
            expecting=None,
            inherit=None,
        )
        assert prompt.name == "my_prompt"
        assert "helpful assistant" in prompt.body

    def test_prompt_def_with_modifiers_creation(self):
        from streetrace.dsl.ast.nodes import PromptDef

        prompt = PromptDef(
            name="analyze_prompt",
            body="Analyze the data.",
            model="compact",
            expecting="AnalysisResult",
            inherit="$history",
        )
        assert prompt.name == "analyze_prompt"
        assert prompt.model == "compact"
        assert prompt.expecting == "AnalysisResult"
        assert prompt.inherit == "$history"

    def test_flow_def_creation(self):
        from streetrace.dsl.ast.nodes import FlowDef, ReturnStmt, VarRef

        flow = FlowDef(
            name="my_workflow",
            params=[],
            body=[ReturnStmt(value=VarRef(name="result"))],
        )
        assert flow.name == "my_workflow"
        assert len(flow.body) == 1

    def test_flow_def_with_params_creation(self):
        from streetrace.dsl.ast.nodes import FlowDef

        flow = FlowDef(
            name="detect_trajectory_drift",
            params=["$goal"],
            body=[],
        )
        assert flow.name == "detect_trajectory_drift"
        assert flow.params == ["$goal"]

    def test_event_handler_creation(self):
        from streetrace.dsl.ast.nodes import EventHandler, MaskAction

        handler = EventHandler(
            timing="on",
            event_type="input",
            body=[MaskAction(guardrail="pii")],
        )
        assert handler.timing == "on"
        assert handler.event_type == "input"
        assert len(handler.body) == 1

    def test_retry_policy_creation(self):
        from streetrace.dsl.ast.nodes import RetryPolicyDef

        policy = RetryPolicyDef(
            name="default",
            times=3,
            backoff_strategy="exponential",
        )
        assert policy.name == "default"
        assert policy.times == 3
        assert policy.backoff_strategy == "exponential"

    def test_timeout_policy_creation(self):
        from streetrace.dsl.ast.nodes import TimeoutPolicyDef

        policy = TimeoutPolicyDef(
            name="default",
            value=30,
            unit="seconds",
        )
        assert policy.name == "default"
        assert policy.value == 30
        assert policy.unit == "seconds"

    def test_policy_def_creation(self):
        from streetrace.dsl.ast.nodes import PolicyDef

        policy = PolicyDef(
            name="compaction",
            properties={
                "trigger": {"var": "token_usage", "op": ">", "value": 0.8},
                "strategy": "summarize_with_goal",
            },
        )
        assert policy.name == "compaction"
        assert "trigger" in policy.properties


class TestExpressionNodes:
    """Test expression AST nodes."""

    def test_var_ref_creation(self):
        from streetrace.dsl.ast.nodes import VarRef

        var = VarRef(name="input")
        assert var.name == "input"

    def test_property_access_creation(self):
        from streetrace.dsl.ast.nodes import PropertyAccess, VarRef

        prop = PropertyAccess(
            base=VarRef(name="item"),
            properties=["value", "first"],
        )
        assert prop.properties == ["value", "first"]

    def test_literal_string_creation(self):
        from streetrace.dsl.ast.nodes import Literal

        lit = Literal(value="hello", literal_type="string")
        assert lit.value == "hello"
        assert lit.literal_type == "string"

    def test_literal_int_creation(self):
        from streetrace.dsl.ast.nodes import Literal

        lit = Literal(value=42, literal_type="int")
        assert lit.value == 42
        assert lit.literal_type == "int"

    def test_literal_float_creation(self):
        from streetrace.dsl.ast.nodes import Literal

        lit = Literal(value=3.14, literal_type="float")
        assert lit.value == 3.14
        assert lit.literal_type == "float"

    def test_literal_bool_creation(self):
        from streetrace.dsl.ast.nodes import Literal

        lit = Literal(value=True, literal_type="bool")
        assert lit.value is True

    def test_binary_op_creation(self):
        from streetrace.dsl.ast.nodes import BinaryOp, Literal

        binary = BinaryOp(
            op=">",
            left=Literal(value=10, literal_type="int"),
            right=Literal(value=5, literal_type="int"),
        )
        assert binary.op == ">"

    def test_unary_op_creation(self):
        from streetrace.dsl.ast.nodes import Literal, UnaryOp

        unary = UnaryOp(
            op="not",
            operand=Literal(value=True, literal_type="bool"),
        )
        assert unary.op == "not"

    def test_function_call_creation(self):
        from streetrace.dsl.ast.nodes import FunctionCall, VarRef

        call = FunctionCall(
            name="lib.convert",
            args=[VarRef(name="item")],
        )
        assert call.name == "lib.convert"
        assert len(call.args) == 1

    def test_list_literal_creation(self):
        from streetrace.dsl.ast.nodes import ListLiteral, Literal

        lst = ListLiteral(
            elements=[
                Literal(value=1, literal_type="int"),
                Literal(value=2, literal_type="int"),
            ],
        )
        assert len(lst.elements) == 2

    def test_object_literal_creation(self):
        from streetrace.dsl.ast.nodes import Literal, ObjectLiteral

        obj = ObjectLiteral(
            entries={
                "success": Literal(value=True, literal_type="bool"),
                "count": Literal(value=42, literal_type="int"),
            },
        )
        assert "success" in obj.entries
        assert "count" in obj.entries


class TestStatementNodes:
    """Test statement AST nodes."""

    def test_assignment_creation(self):
        from streetrace.dsl.ast.nodes import Assignment, Literal

        assign = Assignment(
            target="x",
            value=Literal(value=42, literal_type="int"),
        )
        assert assign.target == "x"

    def test_run_stmt_creation(self):
        from streetrace.dsl.ast.nodes import RunStmt, VarRef

        run = RunStmt(
            target="result",
            agent="fetch_data",
            input=VarRef(name="input"),
        )
        assert run.target == "result"
        assert run.agent == "fetch_data"

    def test_call_stmt_creation(self):
        from streetrace.dsl.ast.nodes import CallStmt, VarRef

        call = CallStmt(
            target="goal",
            prompt="analyze_prompt",
            input=VarRef(name="input"),
            model="compact",
        )
        assert call.target == "goal"
        assert call.prompt == "analyze_prompt"
        assert call.model == "compact"

    def test_return_stmt_creation(self):
        from streetrace.dsl.ast.nodes import ReturnStmt, VarRef

        ret = ReturnStmt(value=VarRef(name="result"))
        assert ret.value is not None

    def test_push_stmt_creation(self):
        from streetrace.dsl.ast.nodes import PushStmt, VarRef

        push = PushStmt(
            value=VarRef(name="item"),
            target="results",
        )
        assert push.target == "results"

    def test_escalate_stmt_creation(self):
        from streetrace.dsl.ast.nodes import EscalateStmt

        escalate = EscalateStmt(message="High priority issue")
        assert escalate.message == "High priority issue"

    def test_log_stmt_creation(self):
        from streetrace.dsl.ast.nodes import LogStmt

        log = LogStmt(message="Processing started")
        assert log.message == "Processing started"


class TestControlFlowNodes:
    """Test control flow AST nodes."""

    def test_for_loop_creation(self):
        from streetrace.dsl.ast.nodes import ForLoop, LogStmt, VarRef

        loop = ForLoop(
            variable="item",
            iterable=VarRef(name="items"),
            body=[LogStmt(message="Processing")],
        )
        assert loop.variable == "item"
        assert len(loop.body) == 1

    def test_parallel_block_creation(self):
        from streetrace.dsl.ast.nodes import ParallelBlock, RunStmt, VarRef

        parallel = ParallelBlock(
            body=[
                RunStmt(
                    target="web",
                    agent="web_search",
                    input=VarRef(name="topic"),
                ),
            ],
        )
        assert len(parallel.body) == 1

    def test_match_block_creation(self):
        from streetrace.dsl.ast.nodes import LogStmt, MatchBlock, MatchCase, VarRef

        match = MatchBlock(
            expression=VarRef(name="type"),
            cases=[
                MatchCase(pattern="standard", body=LogStmt(message="Standard")),
            ],
            else_body=LogStmt(message="Unknown"),
        )
        assert len(match.cases) == 1
        assert match.else_body is not None

    def test_if_block_creation(self):
        from streetrace.dsl.ast.nodes import BinaryOp, IfBlock, Literal, LogStmt, VarRef

        if_block = IfBlock(
            condition=BinaryOp(
                op=">",
                left=VarRef(name="score"),
                right=Literal(value=0.5, literal_type="float"),
            ),
            body=[LogStmt(message="High score")],
        )
        assert len(if_block.body) == 1

    def test_failure_block_creation(self):
        from streetrace.dsl.ast.nodes import FailureBlock, LogStmt

        failure = FailureBlock(
            body=[LogStmt(message="Operation failed")],
        )
        assert len(failure.body) == 1


class TestGuardrailNodes:
    """Test guardrail action AST nodes."""

    def test_mask_action_creation(self):
        from streetrace.dsl.ast.nodes import MaskAction

        mask = MaskAction(guardrail="pii")
        assert mask.guardrail == "pii"

    def test_block_action_creation(self):
        from streetrace.dsl.ast.nodes import BlockAction, VarRef

        block = BlockAction(condition=VarRef(name="jailbreak"))
        assert block.condition is not None

    def test_warn_action_condition_creation(self):
        from streetrace.dsl.ast.nodes import BinaryOp, Literal, VarRef, WarnAction

        warn = WarnAction(
            condition=BinaryOp(
                op="<",
                left=VarRef(name="score"),
                right=Literal(value=0.5, literal_type="float"),
            ),
            message=None,
        )
        assert warn.condition is not None
        assert warn.message is None

    def test_warn_action_message_creation(self):
        from streetrace.dsl.ast.nodes import WarnAction

        warn = WarnAction(
            condition=None,
            message="Check this output",
        )
        assert warn.condition is None
        assert warn.message == "Check this output"

    def test_retry_action_creation(self):
        from streetrace.dsl.ast.nodes import (
            BinaryOp,
            Literal,
            PropertyAccess,
            RetryAction,
            VarRef,
        )

        retry = RetryAction(
            message=PropertyAccess(
                base=VarRef(name="drift"),
                properties=["message"],
            ),
            condition=BinaryOp(
                op=">",
                left=PropertyAccess(
                    base=VarRef(name="drift"),
                    properties=["score"],
                ),
                right=Literal(value=0.2, literal_type="float"),
            ),
        )
        assert retry.message is not None
        assert retry.condition is not None


class TestAstTransformer:
    """Test transformation from parse tree to AST."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_minimal_agent(self, parser):
        from streetrace.dsl.ast.nodes import AgentDef, DslFile, ModelDef, PromptDef
        from streetrace.dsl.ast.transformer import transform

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
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        assert ast.version is None

        # Find model definition
        models = [s for s in ast.statements if isinstance(s, ModelDef)]
        assert len(models) == 1
        assert models[0].name == "main"
        assert models[0].provider_model == "anthropic/claude-sonnet"

        # Find agent definition
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].name is None
        assert agents[0].tools == ["github"]
        assert agents[0].instruction == "my_prompt"

        # Find prompt definition
        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 1
        assert prompts[0].name == "my_prompt"

    def test_transforms_version_declaration(self, parser):
        from streetrace.dsl.ast.nodes import DslFile
        from streetrace.dsl.ast.transformer import transform

        source = """streetrace v1.2

model main = openai/gpt-4
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        assert ast.version is not None
        assert ast.version.version == "v1.2"

    def test_transforms_model_long_form(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, ModelDef
        from streetrace.dsl.ast.transformer import transform

        source = """
model main:
    provider: anthropic
    name: claude-sonnet
    temperature: 0.7
    max_tokens: 4096
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        models = [s for s in ast.statements if isinstance(s, ModelDef)]
        assert len(models) == 1
        assert models[0].name == "main"
        assert models[0].provider_model is None
        assert models[0].properties is not None
        assert models[0].properties["provider"] == "anthropic"
        assert models[0].properties["temperature"] == 0.7

    def test_transforms_schema_definition(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, SchemaDef
        from streetrace.dsl.ast.transformer import transform

        source = """
schema ReviewResult:
    approved: bool
    comments: list[string]
    severity: string?
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        schemas = [s for s in ast.statements if isinstance(s, SchemaDef)]
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema.name == "ReviewResult"
        assert len(schema.fields) == 3

        # Check field types
        approved_field = next(f for f in schema.fields if f.name == "approved")
        assert approved_field.type_expr.base_type == "bool"
        assert approved_field.type_expr.is_list is False

        comments_field = next(f for f in schema.fields if f.name == "comments")
        assert comments_field.type_expr.base_type == "string"
        assert comments_field.type_expr.is_list is True

        severity_field = next(f for f in schema.fields if f.name == "severity")
        assert severity_field.type_expr.base_type == "string"
        assert severity_field.type_expr.is_optional is True

    def test_transforms_tool_mcp_short_form(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, ToolDef
        from streetrace.dsl.ast.transformer import transform

        source = """tool github = mcp "https://api.github.com" with auth bearer "token"
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        tools = [s for s in ast.statements if isinstance(s, ToolDef)]
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "github"
        assert tool.tool_type == "mcp"
        assert tool.url == "https://api.github.com"
        assert tool.auth_type == "bearer"
        assert tool.auth_value == "token"

    def test_transforms_tool_builtin(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, ToolDef
        from streetrace.dsl.ast.transformer import transform

        source = "tool fs = builtin streetrace.fs\n"
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        tools = [s for s in ast.statements if isinstance(s, ToolDef)]
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "fs"
        assert tool.tool_type == "builtin"
        assert tool.builtin_ref == "streetrace.fs"

    def test_transforms_import_statements(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, ImportStmt
        from streetrace.dsl.ast.transformer import transform

        source = """import base from streetrace
import ./custom_agent.sr
import lib from pip://third_party
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        imports = [s for s in ast.statements if isinstance(s, ImportStmt)]
        assert len(imports) == 3

        streetrace_import = next(i for i in imports if i.source_type == "streetrace")
        assert streetrace_import.name == "base"

        local_import = next(i for i in imports if i.source_type == "local")
        assert local_import.source == "./custom_agent.sr"

        pip_import = next(i for i in imports if i.source_type == "pip")
        assert pip_import.name == "lib"

    def test_transforms_retry_policy(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, RetryPolicyDef
        from streetrace.dsl.ast.transformer import transform

        source = "retry default = 3 times, exponential backoff\n"
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, RetryPolicyDef)]
        assert len(policies) == 1
        policy = policies[0]
        assert policy.name == "default"
        assert policy.times == 3
        assert policy.backoff_strategy == "exponential"

    def test_transforms_timeout_policy(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, TimeoutPolicyDef
        from streetrace.dsl.ast.transformer import transform

        source = "timeout default = 2 minutes\n"
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, TimeoutPolicyDef)]
        assert len(policies) == 1
        policy = policies[0]
        assert policy.name == "default"
        assert policy.value == 2
        assert policy.unit == "minutes"

    def test_transforms_event_handler(self, parser):
        from streetrace.dsl.ast.nodes import (
            BlockAction,
            DslFile,
            EventHandler,
            MaskAction,
        )
        from streetrace.dsl.ast.transformer import transform

        source = """
on input do
    mask pii
    block if jailbreak
end
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        handlers = [s for s in ast.statements if isinstance(s, EventHandler)]
        assert len(handlers) == 1
        handler = handlers[0]
        assert handler.timing == "on"
        assert handler.event_type == "input"
        assert len(handler.body) == 2
        assert isinstance(handler.body[0], MaskAction)
        assert isinstance(handler.body[1], BlockAction)

    def test_transforms_flow_with_control_structures(self, parser):
        from streetrace.dsl.ast.nodes import (
            DslFile,
            FlowDef,
            ForLoop,
            PushStmt,
            ReturnStmt,
        )
        from streetrace.dsl.ast.transformer import transform

        source = """
flow process_items:
    $results = []
    for $item in $items do
        $result = run agent process_item with $item
        push $result to $results
    end
    return $results
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]
        assert flow.name == "process_items"

        # Find for loop in flow body
        for_loops = [s for s in flow.body if isinstance(s, ForLoop)]
        assert len(for_loops) == 1
        assert for_loops[0].variable == "item"

        # Find push statement in for loop body
        push_stmts = [s for s in for_loops[0].body if isinstance(s, PushStmt)]
        assert len(push_stmts) == 1

        # Find return statement
        returns = [s for s in flow.body if isinstance(s, ReturnStmt)]
        assert len(returns) == 1

    def test_transforms_prompt_with_modifiers(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, PromptDef
        from streetrace.dsl.ast.transformer import transform

        source = '''
prompt analyze_goal using model "compact" expecting GoalAnalysis: """
You are a work analyst.
"""
'''
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 1
        prompt = prompts[0]
        assert prompt.name == "analyze_goal"
        assert prompt.model == "compact"
        assert prompt.expecting == "GoalAnalysis"

    def test_transforms_complex_expressions(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, EventHandler
        from streetrace.dsl.ast.transformer import transform

        source = """
on output do
    retry with $drift.message if $drift.score > 0.2
end
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        handlers = [s for s in ast.statements if isinstance(s, EventHandler)]
        assert len(handlers) == 1
        handler = handlers[0]

        # The retry action should have a binary comparison condition
        retry_action = handler.body[0]
        assert retry_action.condition is not None

    def test_transforms_match_block(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, FlowDef, MatchBlock
        from streetrace.dsl.ast.transformer import transform

        source = """
flow handle_type:
    match $item.type
        when "standard" -> run agent process_standard with $item
        when "expedited" -> run agent process_expedited with $item
        else -> log "Unknown type"
    end
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]

        match_blocks = [s for s in flow.body if isinstance(s, MatchBlock)]
        assert len(match_blocks) == 1
        match_block = match_blocks[0]
        assert len(match_block.cases) == 2
        assert match_block.else_body is not None

    def test_transforms_parallel_block(self, parser):
        from streetrace.dsl.ast.nodes import DslFile, FlowDef, ParallelBlock
        from streetrace.dsl.ast.transformer import transform

        source = """
flow parallel_search:
    parallel do
        $web_results = run agent web_search with $topic
        $doc_results = run agent doc_search with $topic
    end
    return $web_results
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]

        parallel_blocks = [s for s in flow.body if isinstance(s, ParallelBlock)]
        assert len(parallel_blocks) == 1
        assert len(parallel_blocks[0].body) == 2

    def test_ast_nodes_have_source_position(self, parser):
        from streetrace.dsl.ast.transformer import transform

        source = """
model main = anthropic/claude-sonnet
"""
        tree = parser.parse(source)
        ast = transform(tree)

        # Model should have source position info
        model = ast.statements[0]
        assert hasattr(model, "meta")
        # Meta contains line/column from Lark


class TestAstAllNodeTypesHaveRequiredFields:
    """Verify all AST node types have proper field definitions."""

    def test_all_nodes_are_dataclasses(self):
        from dataclasses import fields, is_dataclass

        from streetrace.dsl.ast import nodes

        node_classes = [
            nodes.DslFile,
            nodes.VersionDecl,
            nodes.ImportStmt,
            nodes.ModelDef,
            nodes.SchemaDef,
            nodes.SchemaField,
            nodes.TypeExpr,
            nodes.ToolDef,
            nodes.AgentDef,
            nodes.PromptDef,
            nodes.FlowDef,
            nodes.EventHandler,
            nodes.RetryPolicyDef,
            nodes.TimeoutPolicyDef,
            nodes.PolicyDef,
            nodes.VarRef,
            nodes.PropertyAccess,
            nodes.Literal,
            nodes.BinaryOp,
            nodes.UnaryOp,
            nodes.FunctionCall,
            nodes.ListLiteral,
            nodes.ObjectLiteral,
            nodes.Assignment,
            nodes.RunStmt,
            nodes.CallStmt,
            nodes.ReturnStmt,
            nodes.PushStmt,
            nodes.EscalateStmt,
            nodes.LogStmt,
            nodes.ForLoop,
            nodes.ParallelBlock,
            nodes.MatchBlock,
            nodes.MatchCase,
            nodes.IfBlock,
            nodes.FailureBlock,
            nodes.MaskAction,
            nodes.BlockAction,
            nodes.WarnAction,
            nodes.RetryAction,
        ]

        for cls in node_classes:
            assert is_dataclass(cls), f"{cls.__name__} should be a dataclass"
            # Verify it has fields (not an empty dataclass)
            assert len(fields(cls)) > 0, f"{cls.__name__} should have fields"
