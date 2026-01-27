"""Tests for escalation-related AST nodes.

Test coverage for EscalationCondition and EscalationHandler nodes,
as well as the modified PromptDef and RunStmt nodes with escalation fields.
"""


from streetrace.dsl.ast.nodes import (
    EscalationCondition,
    EscalationHandler,
    Literal,
    PromptDef,
    RunStmt,
    SourcePosition,
    VarRef,
)


class TestEscalationConditionNode:
    """Test EscalationCondition dataclass creation."""

    def test_creates_normalized_condition(self):
        """Test creating a normalized (~) escalation condition."""
        condition = EscalationCondition(op="~", value="DRIFTING")
        assert condition.op == "~"
        assert condition.value == "DRIFTING"
        assert condition.meta is None

    def test_creates_exact_match_condition(self):
        """Test creating an exact match (==) escalation condition."""
        condition = EscalationCondition(op="==", value="NEEDS_HUMAN")
        assert condition.op == "=="
        assert condition.value == "NEEDS_HUMAN"

    def test_creates_not_equal_condition(self):
        """Test creating a not equal (!=) escalation condition."""
        condition = EscalationCondition(op="!=", value="SUCCESS")
        assert condition.op == "!="
        assert condition.value == "SUCCESS"

    def test_creates_contains_condition(self):
        """Test creating a contains escalation condition."""
        condition = EscalationCondition(op="contains", value="ERROR")
        assert condition.op == "contains"
        assert condition.value == "ERROR"

    def test_creates_condition_with_source_position(self):
        """Test creating a condition with source position metadata."""
        meta = SourcePosition(line=10, column=5, end_line=10, end_column=25)
        condition = EscalationCondition(op="~", value="ESCALATE", meta=meta)
        assert condition.meta is not None
        assert condition.meta.line == 10
        assert condition.meta.column == 5

    def test_creates_condition_with_expression_value(self):
        """Test creating a condition with an AST node value."""
        var_ref = VarRef(name="escalation_keyword")
        condition = EscalationCondition(op="~", value=var_ref)
        assert condition.op == "~"
        assert isinstance(condition.value, VarRef)
        assert condition.value.name == "escalation_keyword"


class TestEscalationHandlerNode:
    """Test EscalationHandler dataclass creation."""

    def test_creates_return_handler(self):
        """Test creating a return escalation handler."""
        value = VarRef(name="current")
        handler = EscalationHandler(action="return", value=value)
        assert handler.action == "return"
        assert isinstance(handler.value, VarRef)
        assert handler.value.name == "current"
        assert handler.meta is None

    def test_creates_continue_handler(self):
        """Test creating a continue escalation handler."""
        handler = EscalationHandler(action="continue")
        assert handler.action == "continue"
        assert handler.value is None

    def test_creates_abort_handler(self):
        """Test creating an abort escalation handler."""
        handler = EscalationHandler(action="abort")
        assert handler.action == "abort"
        assert handler.value is None

    def test_creates_handler_with_source_position(self):
        """Test creating a handler with source position metadata."""
        meta = SourcePosition(line=15, column=10, end_line=15, end_column=40)
        handler = EscalationHandler(action="continue", meta=meta)
        assert handler.meta is not None
        assert handler.meta.line == 15

    def test_creates_return_handler_with_literal_value(self):
        """Test creating a return handler with a literal value."""
        value = Literal(value="fallback result", literal_type="string")
        handler = EscalationHandler(action="return", value=value)
        assert handler.action == "return"
        assert isinstance(handler.value, Literal)
        assert handler.value.value == "fallback result"


class TestPromptDefWithEscalation:
    """Test PromptDef node with escalation_condition field."""

    def test_creates_prompt_without_escalation(self):
        """Test that PromptDef works without escalation (backward compat)."""
        prompt = PromptDef(
            name="my_prompt",
            body="You are a helpful assistant.",
        )
        assert prompt.name == "my_prompt"
        assert prompt.escalation_condition is None

    def test_creates_prompt_with_escalation_condition(self):
        """Test creating a prompt with escalation condition."""
        condition = EscalationCondition(op="~", value="DRIFTING")
        prompt = PromptDef(
            name="pi_enhancer",
            body="You are an AI assistant.",
            escalation_condition=condition,
        )
        assert prompt.name == "pi_enhancer"
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "~"
        assert prompt.escalation_condition.value == "DRIFTING"

    def test_creates_prompt_with_all_fields(self):
        """Test creating a prompt with all fields including escalation."""
        condition = EscalationCondition(op="contains", value="ESCALATE")
        prompt = PromptDef(
            name="analyzer",
            body="Analyze the input.",
            model="compact",
            expecting="AnalysisResult",
            inherit="$history",
            escalation_condition=condition,
        )
        assert prompt.name == "analyzer"
        assert prompt.model == "compact"
        assert prompt.expecting == "AnalysisResult"
        assert prompt.inherit == "$history"
        assert prompt.escalation_condition.op == "contains"


class TestRunStmtWithEscalation:
    """Test RunStmt node with escalation_handler field."""

    def test_creates_run_stmt_without_escalation(self):
        """Test that RunStmt works without escalation handler (backward compat)."""
        run = RunStmt(
            target="$result",
            agent="fetch_data",
            args=[VarRef(name="input")],
        )
        assert run.target == "$result"
        assert run.agent == "fetch_data"
        assert run.escalation_handler is None

    def test_creates_run_stmt_with_return_handler(self):
        """Test creating a run statement with return escalation handler."""
        handler = EscalationHandler(action="return", value=VarRef(name="current"))
        run = RunStmt(
            target="$current",
            agent="peer1",
            args=[VarRef(name="current")],
            escalation_handler=handler,
        )
        assert run.escalation_handler is not None
        assert run.escalation_handler.action == "return"
        assert run.escalation_handler.value.name == "current"

    def test_creates_run_stmt_with_continue_handler(self):
        """Test creating a run statement with continue escalation handler."""
        handler = EscalationHandler(action="continue")
        run = RunStmt(
            target="$data",
            agent="validator",
            args=[VarRef(name="data")],
            escalation_handler=handler,
        )
        assert run.escalation_handler is not None
        assert run.escalation_handler.action == "continue"

    def test_creates_run_stmt_with_abort_handler(self):
        """Test creating a run statement with abort escalation handler."""
        handler = EscalationHandler(action="abort")
        run = RunStmt(
            target="$result",
            agent="processor",
            args=[VarRef(name="input")],
            escalation_handler=handler,
        )
        assert run.escalation_handler is not None
        assert run.escalation_handler.action == "abort"

    def test_creates_flow_run_stmt_with_escalation(self):
        """Test creating a flow run statement with escalation handler."""
        handler = EscalationHandler(action="return", value=VarRef(name="fallback"))
        run = RunStmt(
            target="$result",
            agent="process_flow",
            args=[],
            is_flow=True,
            escalation_handler=handler,
        )
        assert run.is_flow is True
        assert run.escalation_handler is not None


class TestEscalationNodesAreDataclasses:
    """Verify escalation nodes are proper dataclasses."""

    def test_escalation_condition_is_dataclass(self):
        """Test that EscalationCondition is a dataclass."""
        from dataclasses import fields, is_dataclass

        assert is_dataclass(EscalationCondition)
        field_names = [f.name for f in fields(EscalationCondition)]
        assert "op" in field_names
        assert "value" in field_names
        assert "meta" in field_names

    def test_escalation_handler_is_dataclass(self):
        """Test that EscalationHandler is a dataclass."""
        from dataclasses import fields, is_dataclass

        assert is_dataclass(EscalationHandler)
        field_names = [f.name for f in fields(EscalationHandler)]
        assert "action" in field_names
        assert "value" in field_names
        assert "meta" in field_names
