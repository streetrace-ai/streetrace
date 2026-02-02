"""Tests for prompt override pattern in Streetrace DSL.

Test the ability to define prompts multiple times with later definitions
overriding/completing earlier ones. This enables better file organization
with declarations at the top and body definitions at the bottom.
"""

from streetrace.dsl.ast import (
    DslFile,
    EscalationCondition,
    ModelDef,
    PromptDef,
    SchemaDef,
    SchemaField,
    SourcePosition,
    TypeExpr,
    VersionDecl,
)
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.errors import ErrorCode


def _make_schema(name: str) -> SchemaDef:
    """Create a simple test schema."""
    return SchemaDef(
        name=name,
        fields=[SchemaField(name="value", type_expr=TypeExpr(base_type="string"))],
    )


class TestPromptOverrideBasic:
    """Test basic prompt override functionality."""

    def test_declaration_then_body(self) -> None:
        """Declaration followed by body definition merges correctly."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                _make_schema("Schema"),
                # Declaration at top - modifiers only
                PromptDef(
                    name="reviewer",
                    body="",
                    model="main",
                    expecting="Schema",
                ),
                # Body definition at bottom
                PromptDef(
                    name="reviewer",
                    body="You are a code reviewer.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        # Merged prompt should have both body and modifiers
        merged = result.symbols.prompts["reviewer"]
        assert merged.body == "You are a code reviewer."
        assert merged.model == "main"
        assert merged.expecting == "Schema"

    def test_body_then_declaration(self) -> None:
        """Body first, then declaration - order doesn't matter."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="fast", provider_model="anthropic/claude-haiku"),
                # Body definition first
                PromptDef(
                    name="analyzer",
                    body="Analyze the code.",
                ),
                # Declaration adds modifiers
                PromptDef(
                    name="analyzer",
                    body="",
                    model="fast",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["analyzer"]
        assert merged.body == "Analyze the code."
        assert merged.model == "fast"

    def test_body_overwrites_earlier_body(self) -> None:
        """Later body definition overwrites earlier body."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="prompt",
                    body="First body.",
                ),
                PromptDef(
                    name="prompt",
                    body="Second body.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.body == "Second body."


class TestPromptOverrideModifiers:
    """Test modifier merging in prompt overrides."""

    def test_modifiers_fill_not_set(self) -> None:
        """Later modifiers fill in missing values from earlier."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                _make_schema("Result"),
                PromptDef(
                    name="prompt",
                    body="",
                    model="main",
                ),
                PromptDef(
                    name="prompt",
                    body="Body text.",
                    expecting="Result",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.model == "main"
        assert merged.expecting == "Result"
        assert merged.body == "Body text."

    def test_same_modifier_values_ok(self) -> None:
        """Same modifier values in multiple definitions is fine."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                PromptDef(
                    name="prompt",
                    body="",
                    model="main",
                ),
                PromptDef(
                    name="prompt",
                    body="Body.",
                    model="main",  # Same value - OK
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

    def test_inherit_modifier_merges(self) -> None:
        """Inherit modifier merges correctly."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="prompt",
                    body="",
                    inherit="$context",
                ),
                PromptDef(
                    name="prompt",
                    body="Body text.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.inherit == "$context"


class TestPromptOverrideErrors:
    """Test error detection in prompt overrides."""

    def test_conflicting_model_error(self) -> None:
        """Different model values trigger E0014 error."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                ModelDef(name="fast", provider_model="anthropic/claude-haiku"),
                PromptDef(
                    name="prompt",
                    body="",
                    model="main",
                    meta=SourcePosition(line=5, column=1),
                ),
                PromptDef(
                    name="prompt",
                    body="Body.",
                    model="fast",  # Conflict!
                    meta=SourcePosition(line=10, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0014 for e in result.errors)
        conflict_error = next(e for e in result.errors if e.code == ErrorCode.E0014)
        assert "model" in conflict_error.message
        assert "main" in conflict_error.message
        assert "fast" in conflict_error.message

    def test_conflicting_expecting_error(self) -> None:
        """Different expecting values trigger E0014 error."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="prompt",
                    body="Body.",
                    expecting="Schema1",
                ),
                PromptDef(
                    name="prompt",
                    body="",
                    expecting="Schema2",  # Conflict!
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0014 for e in result.errors)

    def test_missing_body_error(self) -> None:
        """Declarations only without body trigger E0013 error."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                PromptDef(
                    name="orphan",
                    body="",  # No body!
                    model="main",
                    meta=SourcePosition(line=3, column=1),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0013 for e in result.errors)
        missing_body_error = next(e for e in result.errors if e.code == ErrorCode.E0013)
        assert "orphan" in missing_body_error.message
        assert "body" in missing_body_error.message

    def test_multiple_declarations_no_body_error(self) -> None:
        """Multiple declarations all without body trigger E0013."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                PromptDef(name="prompt", body="", model="main"),
                PromptDef(name="prompt", body="", expecting="Schema"),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0013 for e in result.errors)


class TestPromptOverrideMultiple:
    """Test multiple overrides."""

    def test_three_definitions_merge(self) -> None:
        """Three definitions merge correctly."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                _make_schema("Schema"),
                PromptDef(name="prompt", body="", model="main"),
                PromptDef(name="prompt", body="", expecting="Schema"),
                PromptDef(name="prompt", body="Final body."),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.body == "Final body."
        assert merged.model == "main"
        assert merged.expecting == "Schema"

    def test_middle_body_not_overwritten_by_empty(self) -> None:
        """Body in middle definition is kept if later has empty body."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                _make_schema("Schema"),
                PromptDef(name="prompt", body="", model="main"),
                PromptDef(name="prompt", body="Middle body."),
                PromptDef(name="prompt", body="", expecting="Schema"),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.body == "Middle body."

    def test_last_body_wins(self) -> None:
        """Last non-empty body wins."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(name="prompt", body="First body."),
                PromptDef(name="prompt", body="Second body."),
                PromptDef(name="prompt", body="Third body."),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.body == "Third body."


class TestPromptOverrideEscalation:
    """Test escalation condition handling in prompt overrides."""

    def test_escalation_from_declaration_preserved(self) -> None:
        """Escalation from earlier definition is preserved if later has none."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="prompt",
                    body="",
                    escalation_condition=EscalationCondition(op="~", value="yes"),
                ),
                PromptDef(
                    name="prompt",
                    body="Body text.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.escalation_condition is not None
        assert merged.escalation_condition.op == "~"
        assert merged.escalation_condition.value == "yes"

    def test_later_escalation_overwrites(self) -> None:
        """Later escalation condition overwrites earlier."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="prompt",
                    body="Body.",
                    escalation_condition=EscalationCondition(op="==", value="abort"),
                ),
                PromptDef(
                    name="prompt",
                    body="",
                    escalation_condition=EscalationCondition(op="~", value="stop"),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["prompt"]
        assert merged.escalation_condition.op == "~"
        assert merged.escalation_condition.value == "stop"


class TestPromptOverrideEndToEnd:
    """End-to-end tests parsing actual DSL source code."""

    def test_parse_declaration_then_body(self) -> None:
        """Parse DSL with declaration followed by body definition."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model main = anthropic/claude-sonnet

schema ReviewResult:
    summary: string
    passed: bool

# Declaration at top - metadata only
prompt reviewer expecting ReviewResult using model "main"

# Full definition at bottom - body text
prompt reviewer: """You are a code reviewer.
Analyze the code and provide feedback.
"""
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_parse_body_then_declaration(self) -> None:
        """Parse DSL with body first, then declaration."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model fast = anthropic/claude-haiku

# Body definition first
prompt analyzer: """Analyze this code."""

# Declaration adds model
prompt analyzer using model "fast"
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_parse_conflicting_modifiers_error(self) -> None:
        """Parse DSL with conflicting modifiers reports error."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku

prompt reviewer using model "main"
prompt reviewer using model "fast": """Body."""
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) > 0
        # Check for conflict error (E0014)
        has_conflict_error = any(
            "conflict" in e.message.lower() or "E0014" in str(e.code)
            for e in errors
        )
        assert has_conflict_error

    def test_parse_missing_body_error(self) -> None:
        """Parse DSL with declaration only (no body) reports error."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = """streetrace v1

model main = anthropic/claude-sonnet

# Only declaration, no body anywhere
prompt orphan using model "main"
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) > 0
        # Check for missing body error (E0013)
        has_missing_body_error = any(
            "body" in e.message.lower() or "E0013" in str(e.code)
            for e in errors
        )
        assert has_missing_body_error

    def test_parse_realistic_file_structure(self) -> None:
        """Parse DSL structured like the v2-parallel.sr example."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku

schema Finding:
    file: string
    line: int
    severity: string

# Declarations with metadata at top
prompt security_reviewer expecting Finding using model "main"
prompt bug_reviewer expecting Finding using model "main"
prompt style_reviewer expecting Finding using model "fast"

# Agents reference prompts
agent security_agent:
    instruction security_reviewer
    description "Security specialist"

agent bug_agent:
    instruction bug_reviewer
    description "Bug detector"

flow main:
    $result = run agent security_agent with $input_prompt
    return $result

# Bodies at bottom
prompt security_reviewer: """You are a SECURITY SPECIALIST.
Review code for vulnerabilities.
"""

prompt bug_reviewer: """You are a BUG DETECTOR.
Find logic errors and runtime issues.
"""

prompt style_reviewer: """You are a QUALITY REVIEWER.
Check for maintainability issues.
"""
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 0


class TestPromptOverrideCodeGeneration:
    """Test that code generation uses merged prompts correctly.

    This ensures the bug where code generator used raw AST prompts
    (losing merged attributes like 'expecting') doesn't regress.
    """

    def test_codegen_uses_merged_expecting(self) -> None:
        """Generated code has schema from declaration when body is separate."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Result:
    value: string

# Declaration with expecting
prompt reviewer expecting Result

# Body definition later
prompt reviewer: """Review the code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

        # Generate code WITH merged prompts (the fix)
        generator = CodeGenerator()
        python_source, _ = generator.generate(
            ast,
            "test.sr",
            merged_prompts=result.symbols.prompts,
        )

        # Verify the generated code has the schema
        assert "schema='Result'" in python_source

    def test_codegen_uses_merged_model(self) -> None:
        """Generated code has model from declaration when body is separate."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

model fast = anthropic/claude-haiku

# Declaration with model
prompt analyzer using model "fast"

# Body definition later
prompt analyzer: """Analyze this."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

        generator = CodeGenerator()
        python_source, _ = generator.generate(
            ast,
            "test.sr",
            merged_prompts=result.symbols.prompts,
        )

        # Verify prompt_models mapping is generated
        assert "'analyzer': 'fast'" in python_source

    def test_codegen_without_merged_prompts_has_duplicate_keys(self) -> None:
        """Without merged_prompts, code generator emits duplicate dict keys.

        This documents the bug that merged_prompts fixes: when the same prompt
        is defined twice (declaration then body), Python dict keeps only the
        last value, losing the schema from the declaration.
        """
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Result:
    value: string

prompt reviewer expecting Result
prompt reviewer: """Body text."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        # Generate WITHOUT merged prompts (old buggy behavior)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        # Both definitions appear, but Python dict keeps only the last one
        # Count occurrences of 'reviewer' key in the _prompts dict
        reviewer_count = python_source.count("'reviewer': PromptSpec")
        assert reviewer_count == 2, "Without merge, both definitions are emitted"

        # The LAST one (body definition) doesn't have schema
        # Find the last occurrence and verify it lacks schema
        last_reviewer_idx = python_source.rfind("'reviewer': PromptSpec")
        next_entry_or_end = python_source.find("'", last_reviewer_idx + 30)
        last_reviewer_section = python_source[last_reviewer_idx:next_entry_or_end]
        assert "schema=" not in last_reviewer_section, (
            "Last definition (which Python uses) should lack schema"
        )
