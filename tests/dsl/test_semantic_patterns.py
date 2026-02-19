"""Tests for semantic analysis of agentic patterns.

Test the semantic analyzer's validation of delegate, use, and loop patterns
including reference validation, circular reference detection, and warnings.
"""

from streetrace.dsl.ast import (
    AgentDef,
    Assignment,
    DslFile,
    Literal,
    LoopBlock,
    PromptDef,
    ReturnStmt,
    SourcePosition,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.errors import ErrorCode

# =============================================================================
# Delegate Reference Validation Tests
# =============================================================================


class TestDelegateReferenceValidation:
    """Test validation of agent delegate references."""

    def test_valid_delegate_passes(self) -> None:
        """Agent with valid delegate reference passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="worker_prompt", body="Do work"),
                PromptDef(name="coord_prompt", body="Coordinate work"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker"],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_delegate_multiple_agents_passes(self) -> None:
        """Agent with multiple valid delegate references passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="worker1_prompt", body="Do work 1"),
                PromptDef(name="worker2_prompt", body="Do work 2"),
                PromptDef(name="coord_prompt", body="Coordinate work"),
                AgentDef(
                    name="worker1",
                    tools=[],
                    instruction="worker1_prompt",
                ),
                AgentDef(
                    name="worker2",
                    tools=[],
                    instruction="worker2_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker1", "worker2"],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_undefined_delegate_error(self) -> None:
        """Undefined delegate reference produces E0001 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="coord_prompt", body="Coordinate work"),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["undefined_agent"],
                    meta=SourcePosition(line=5, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert len(e0001_errors) >= 1
        assert any("undefined_agent" in e.message for e in e0001_errors)

    def test_undefined_delegate_with_suggestion(self) -> None:
        """Undefined delegate error includes suggestion when similar agent exists."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="worker_prompt", body="Do work"),
                PromptDef(name="coord_prompt", body="Coordinate work"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["workr"],  # Typo
                    meta=SourcePosition(line=10, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert len(e0001_errors) >= 1
        # Should have a suggestion
        assert any(e.suggestion is not None for e in e0001_errors)


# =============================================================================
# Use Reference Validation Tests
# =============================================================================


class TestUseReferenceValidation:
    """Test validation of agent use references."""

    def test_valid_use_passes(self) -> None:
        """Agent with valid use reference passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="helper_prompt", body="Help with tasks"),
                PromptDef(name="main_prompt", body="Main agent"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper"],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_use_multiple_agents_passes(self) -> None:
        """Agent with multiple valid use references passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="helper1_prompt", body="Help 1"),
                PromptDef(name="helper2_prompt", body="Help 2"),
                PromptDef(name="main_prompt", body="Main agent"),
                AgentDef(
                    name="helper1",
                    tools=[],
                    instruction="helper1_prompt",
                ),
                AgentDef(
                    name="helper2",
                    tools=[],
                    instruction="helper2_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper1", "helper2"],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_undefined_use_error(self) -> None:
        """Undefined use reference produces E0001 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="main_prompt", body="Main agent"),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["undefined_helper"],
                    meta=SourcePosition(line=5, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert len(e0001_errors) >= 1
        assert any("undefined_helper" in e.message for e in e0001_errors)


# =============================================================================
# Circular Reference Detection Tests
# =============================================================================


class TestCircularReferenceDetection:
    """Test detection of circular agent references."""

    def test_circular_delegate_error(self) -> None:
        """Circular delegate reference produces E0011 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_a_prompt", body="Agent A"),
                PromptDef(name="agent_b_prompt", body="Agent B"),
                AgentDef(
                    name="agent_a",
                    tools=[],
                    instruction="agent_a_prompt",
                    delegate=["agent_b"],
                ),
                AgentDef(
                    name="agent_b",
                    tools=[],
                    instruction="agent_b_prompt",
                    delegate=["agent_a"],  # Circular!
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) >= 1
        error_message = e0011_errors[0].message.lower()
        assert "circular" in error_message

    def test_circular_use_error(self) -> None:
        """Circular use reference produces E0011 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_a_prompt", body="Agent A"),
                PromptDef(name="agent_b_prompt", body="Agent B"),
                AgentDef(
                    name="agent_a",
                    tools=[],
                    instruction="agent_a_prompt",
                    use=["agent_b"],
                ),
                AgentDef(
                    name="agent_b",
                    tools=[],
                    instruction="agent_b_prompt",
                    use=["agent_a"],  # Circular!
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) >= 1
        error_message = e0011_errors[0].message.lower()
        assert "circular" in error_message

    def test_self_reference_via_use_allowed(self) -> None:
        """Agent using itself is allowed (recursive tool pattern)."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Self-referencing agent"),
                AgentDef(
                    name="self_agent",
                    tools=[],
                    instruction="agent_prompt",
                    use=["self_agent"],  # Self-reference via use — allowed
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) == 0

    def test_self_reference_via_delegate_error(self) -> None:
        """Agent delegating to itself produces E0011 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Self-referencing agent"),
                AgentDef(
                    name="self_agent",
                    tools=[],
                    instruction="agent_prompt",
                    delegate=["self_agent"],  # Self-reference via delegate — error
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) >= 1
        error_message = e0011_errors[0].message.lower()
        assert "circular" in error_message

    def test_longer_circular_chain_error(self) -> None:
        """Longer circular chain (A -> B -> C -> A) produces E0011 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="a_prompt", body="Agent A"),
                PromptDef(name="b_prompt", body="Agent B"),
                PromptDef(name="c_prompt", body="Agent C"),
                AgentDef(
                    name="agent_a",
                    tools=[],
                    instruction="a_prompt",
                    delegate=["agent_b"],
                ),
                AgentDef(
                    name="agent_b",
                    tools=[],
                    instruction="b_prompt",
                    delegate=["agent_c"],
                ),
                AgentDef(
                    name="agent_c",
                    tools=[],
                    instruction="c_prompt",
                    delegate=["agent_a"],  # Completes the cycle
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) >= 1

    def test_mixed_delegate_use_circular_error(self) -> None:
        """Mixed delegate/use circular reference produces E0011 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_a_prompt", body="Agent A"),
                PromptDef(name="agent_b_prompt", body="Agent B"),
                AgentDef(
                    name="agent_a",
                    tools=[],
                    instruction="agent_a_prompt",
                    delegate=["agent_b"],
                ),
                AgentDef(
                    name="agent_b",
                    tools=[],
                    instruction="agent_b_prompt",
                    use=["agent_a"],  # Circular via use!
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0011_errors = [e for e in result.errors if e.code == ErrorCode.E0011]
        assert len(e0011_errors) >= 1


# =============================================================================
# Warning Tests
# =============================================================================


class TestAgentPatternWarnings:
    """Test warnings for unusual agent patterns."""

    def test_agent_with_both_delegate_and_use_warning(self) -> None:
        """Agent with both delegate and use produces W0002 warning."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="helper_prompt", body="Helper"),
                PromptDef(name="worker_prompt", body="Worker"),
                PromptDef(name="main_prompt", body="Main agent"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    delegate=["worker"],
                    use=["helper"],  # Both delegate and use
                    meta=SourcePosition(line=15, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Should still be valid (warning, not error)
        # But should have a warning
        w0002_warnings = [e for e in result.errors if e.code == ErrorCode.W0002]
        assert len(w0002_warnings) == 1
        warning = w0002_warnings[0]
        assert warning.is_warning is True
        assert "main_agent" in warning.message


# =============================================================================
# Loop Block Validation Tests
# =============================================================================


class TestLoopBlockValidation:
    """Test validation of loop blocks."""

    def test_loop_block_validation_passes(self) -> None:
        """Loop block with valid body passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="analyze", body="Analyze input"),
                AgentDef(
                    name="analyzer",
                    tools=[],
                    instruction="analyze",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_loop_block_with_valid_statements_in_flow(self) -> None:
        """Loop block with valid statements in flow body passes validation."""
        from streetrace.dsl.ast import FlowDef

        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="iterative_flow",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=5,
                            body=[
                                Assignment(
                                    target="counter",
                                    value=Literal(value=0, literal_type="int"),
                                ),
                                ReturnStmt(value=VarRef(name="counter")),
                            ],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_loop_block_with_undefined_variable_error(self) -> None:
        """Loop block referencing undefined variable produces error."""
        from streetrace.dsl.ast import FlowDef

        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="iterative_flow",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=5,
                            body=[
                                ReturnStmt(value=VarRef(name="undefined_var")),
                            ],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_var" in e.message for e in result.errors)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases for pattern validation."""

    def test_empty_delegate_list_passes(self) -> None:
        """Agent with empty delegate list passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    delegate=[],  # Empty list
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_empty_use_list_passes(self) -> None:
        """Agent with empty use list passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    use=[],  # Empty list
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_none_delegate_passes(self) -> None:
        """Agent with None delegate passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    delegate=None,
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_none_use_passes(self) -> None:
        """Agent with None use passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    use=None,
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_acyclic_graph_passes(self) -> None:
        """Valid acyclic delegation graph passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="leaf1_prompt", body="Leaf 1"),
                PromptDef(name="leaf2_prompt", body="Leaf 2"),
                PromptDef(name="mid_prompt", body="Middle"),
                PromptDef(name="root_prompt", body="Root"),
                AgentDef(
                    name="leaf1",
                    tools=[],
                    instruction="leaf1_prompt",
                ),
                AgentDef(
                    name="leaf2",
                    tools=[],
                    instruction="leaf2_prompt",
                ),
                AgentDef(
                    name="middle",
                    tools=[],
                    instruction="mid_prompt",
                    delegate=["leaf1", "leaf2"],
                ),
                AgentDef(
                    name="root",
                    tools=[],
                    instruction="root_prompt",
                    delegate=["middle"],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid


# =============================================================================
# Prompt Variable Validation Tests
# =============================================================================


class TestPromptVariableValidation:
    """Test validation of variable references in prompt bodies."""

    def test_unknown_variable_passes_when_no_similar_match(self) -> None:
        """Unknown variable without similar match passes (assumed runtime var)."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="test_prompt",
                    body="Hello $chunk_data!",  # No similar prompt/produces
                    meta=SourcePosition(line=1, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Passes because no similar symbol suggests it's a runtime variable
        assert result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_typo_of_prompt_produces_error(self) -> None:
        """Typo of a defined prompt produces E0015 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="helper_prompt", body="Helper"),
                PromptDef(
                    name="test_prompt",
                    body="Use $helpr_prompt here",  # Typo of helper_prompt
                    meta=SourcePosition(line=2, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 1
        assert "helpr_prompt" in e0015_errors[0].message
        assert e0015_errors[0].suggestion is not None
        assert "helper_prompt" in e0015_errors[0].suggestion

    def test_builtin_variable_valid(self) -> None:
        """Built-in variables are valid in prompt bodies."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="test_prompt",
                    body="Input: $input_prompt, Session: $session_id",
                    meta=SourcePosition(line=1, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_prompt_composition_valid(self) -> None:
        """Referencing other prompts is valid in prompt bodies."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="helper_prompt",
                    body="Be helpful and concise.",
                ),
                PromptDef(
                    name="main_prompt",
                    body="$helper_prompt Now answer the question.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_produces_variable_valid(self) -> None:
        """Agent produces names are valid in prompts."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="fetcher_prompt", body="Fetch context"),
                PromptDef(
                    name="reviewer_prompt",
                    body="Review using context: $pr_context",
                ),
                AgentDef(
                    name="context_fetcher",
                    tools=[],
                    instruction="fetcher_prompt",
                    produces="pr_context",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_property_access_validates_base(self) -> None:
        """Property access validates the base variable name."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="fetcher_prompt", body="Fetch data"),
                PromptDef(
                    name="test_prompt",
                    body="File: $finding.file, Line: $finding.line_start",
                ),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="fetcher_prompt",
                    produces="finding",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_unknown_property_access_passes(self) -> None:
        """Unknown base variable with property access passes (runtime var)."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="test_prompt",
                    body="Value: $chunk.property",  # chunk is a runtime loop var
                    meta=SourcePosition(line=1, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Passes because 'chunk' doesn't match any known symbol closely
        assert result.is_valid

    def test_typo_property_access_errors(self) -> None:
        """Typo of a known symbol with property access produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="chunk_data", body="Chunk data"),
                PromptDef(
                    name="test_prompt",
                    body="Value: $chunk_dat.property",  # Typo of chunk_data
                    meta=SourcePosition(line=2, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 1
        assert "chunk_dat" in e0015_errors[0].message

    def test_braced_variable_syntax_passes_when_unknown(self) -> None:
        """Braced variable syntax ${var} passes for unknown runtime vars."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="test_prompt",
                    body="Hello ${runtime_var}!",
                    meta=SourcePosition(line=1, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Passes because no similar symbol
        assert result.is_valid

    def test_empty_prompt_body_passes(self) -> None:
        """Empty prompt body passes validation (no variables to check)."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="empty_prompt",
                    body="",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Empty body prompt will fail E0013 (prompt missing body) but not E0015
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 0

    def test_typo_of_produces_name_errors(self) -> None:
        """Typo of an agent produces name produces E0015 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="fetcher_prompt", body="Fetch"),
                PromptDef(
                    name="reviewer_prompt",
                    body="Use $pr_contxt here",  # Typo of pr_context
                    meta=SourcePosition(line=2, column=1),
                ),
                AgentDef(
                    name="context_fetcher",
                    tools=[],
                    instruction="fetcher_prompt",
                    produces="pr_context",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0015_errors = [e for e in result.errors if e.code == ErrorCode.E0015]
        assert len(e0015_errors) == 1
        assert "pr_contxt" in e0015_errors[0].message
        assert e0015_errors[0].suggestion is not None
        assert "pr_context" in e0015_errors[0].suggestion


# =============================================================================
# Instruction Prompt Validation Tests
# =============================================================================


class TestInstructionPromptValidation:
    """Test validation of variables in instruction prompts."""

    def test_runtime_variable_in_instruction_errors(self) -> None:
        """Runtime variable in instruction prompt produces E0016 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="my_instruction",
                    body="Process this: $runtime_var",
                    meta=SourcePosition(line=1, column=1),
                ),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="my_instruction",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0016_errors = [e for e in result.errors if e.code == ErrorCode.E0016]
        assert len(e0016_errors) == 1
        assert "runtime_var" in e0016_errors[0].message
        assert "my_instruction" in e0016_errors[0].message
        assert "my_agent" in e0016_errors[0].message

    def test_prompt_composition_in_instruction_valid(self) -> None:
        """Prompt composition in instruction is valid."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="shared_rules", body="Follow these rules."),
                PromptDef(
                    name="my_instruction",
                    body="$shared_rules Now do the work.",
                ),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="my_instruction",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        e0016_errors = [e for e in result.errors if e.code == ErrorCode.E0016]
        assert len(e0016_errors) == 0

    def test_multiple_runtime_vars_in_instruction(self) -> None:
        """Multiple runtime variables in instruction produce multiple errors."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="my_instruction",
                    body="Context: $context\nData: $data\nItem: $item.property",
                    meta=SourcePosition(line=1, column=1),
                ),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="my_instruction",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        e0016_errors = [e for e in result.errors if e.code == ErrorCode.E0016]
        assert len(e0016_errors) == 3
        error_messages = " ".join(e.message for e in e0016_errors)
        assert "context" in error_messages
        assert "data" in error_messages
        assert "item" in error_messages

    def test_non_instruction_prompt_allows_runtime_vars(self) -> None:
        """Prompts not used as instructions can have runtime variables."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="static_instruction", body="Do the work."),
                PromptDef(
                    name="runtime_prompt",
                    body="Process: $data with $context",  # Runtime vars OK here
                ),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="static_instruction",
                    prompt="runtime_prompt",  # This prompt is resolved at runtime
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        # Should pass - runtime_prompt is not an instruction
        assert result.is_valid
        e0016_errors = [e for e in result.errors if e.code == ErrorCode.E0016]
        assert len(e0016_errors) == 0
