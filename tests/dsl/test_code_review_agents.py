"""Tests for code review agent DSL files.

Verify that all three code review agents compile successfully with the new DSL features:
1. Parse correctly
2. Transform to valid AST
3. Pass semantic validation
4. Generate valid Python code
5. Generated code contains expected patterns for DSL features used
"""

from pathlib import Path

import pytest

from streetrace.dsl import validate_dsl
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory

# Path to code review agents
CODE_REVIEW_DIR = Path(__file__).parent.parent.parent / "agents" / "code-review"

# Agent files and their expected DSL features
AGENT_FILES = [
    (
        "v1-monolithic",
        CODE_REVIEW_DIR / "v1-monolithic.sr",
        ["parallel do", "filter", "property assignment"],
    ),
    (
        "v2-parallel",
        CODE_REVIEW_DIR / "v2-parallel.sr",
        ["parallel do", "filter", "list concatenation"],
    ),
    (
        "v3-hierarchical",
        CODE_REVIEW_DIR / "v3-hierarchical.sr",
        ["use keyword"],
    ),
]


@pytest.fixture
def parser() -> ParserFactory:
    """Create DSL parser instance."""
    return ParserFactory.create()


class TestCodeReviewAgentsParsing:
    """Test that all code review agent files parse correctly."""

    @pytest.mark.parametrize(
        ("name", "path", "features"),
        AGENT_FILES,
        ids=[name for name, _, _ in AGENT_FILES],
    )
    def test_agent_file_parses(
        self,
        name: str,
        path: Path,
        features: list[str],  # noqa: ARG002  # noqa: ARG002
        parser: ParserFactory,
    ) -> None:
        """Code review agent files should parse without errors."""
        if not path.exists():
            pytest.skip(f"{name}.sr not found at {path}")

        source = path.read_text()
        try:
            tree = parser.parse(source)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"Failed to parse {name}.sr: {e}")
        else:
            assert tree is not None, f"Failed to parse {name}.sr"
            assert tree.data == "start", (
                f"Parse tree root should be 'start' for {name}.sr"
            )


class TestCodeReviewAgentsTransformation:
    """Test that all code review agent files transform to valid AST."""

    @pytest.mark.parametrize(
        ("name", "path", "features"),
        AGENT_FILES,
        ids=[name for name, _, _ in AGENT_FILES],
    )
    def test_agent_file_transforms(
        self,
        name: str,
        path: Path,
        features: list[str],  # noqa: ARG002
        parser: ParserFactory,
    ) -> None:
        """Code review agent files should transform to valid AST."""
        if not path.exists():
            pytest.skip(f"{name}.sr not found at {path}")

        source = path.read_text()
        tree = parser.parse(source)

        try:
            ast = transform(tree)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"Failed to transform {name}.sr to AST: {e}")
        else:
            assert ast is not None, f"AST should not be None for {name}.sr"
            assert ast.version is not None, (
                f"AST version should not be None for {name}.sr"
            )
            assert len(ast.statements) > 0, (
                f"AST should have statements for {name}.sr"
            )


class TestCodeReviewAgentsSemanticValidation:
    """Test that all code review agent files pass semantic validation."""

    @pytest.mark.parametrize(
        ("name", "path", "features"),
        AGENT_FILES,
        ids=[name for name, _, _ in AGENT_FILES],
    )
    def test_agent_file_validates(
        self,
        name: str,
        path: Path,
        features: list[str],  # noqa: ARG002
    ) -> None:
        """Code review agent files should pass semantic validation."""
        if not path.exists():
            pytest.skip(f"{name}.sr not found at {path}")

        source = path.read_text()
        diagnostics = validate_dsl(source, f"{name}.sr")
        errors = [d for d in diagnostics if d.severity.name.lower() == "error"]

        assert not errors, (
            f"Agent '{name}.sr' has semantic errors: "
            f"{[f'{e.message} at line {e.line}' for e in errors]}"
        )


class TestCodeReviewAgentsCodeGeneration:
    """Test that all code review agent files generate valid Python code."""

    @pytest.mark.parametrize(
        ("name", "path", "features"),
        AGENT_FILES,
        ids=[name for name, _, _ in AGENT_FILES],
    )
    def test_agent_file_generates_python(
        self,
        name: str,
        path: Path,
        features: list[str],  # noqa: ARG002
        parser: ParserFactory,
    ) -> None:
        """Code review agent files should generate valid Python code."""
        if not path.exists():
            pytest.skip(f"{name}.sr not found at {path}")

        source = path.read_text()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        try:
            python_source, source_mappings = generator.generate(ast, f"{name}.sr")
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"Failed to generate Python for {name}.sr: {e}")

        # Verify Python code is non-empty
        assert python_source, f"Generated Python for {name}.sr should not be empty"

        # Verify Python code compiles without syntax errors
        try:
            compile(python_source, f"<dsl:{name}.sr>", "exec")
        except SyntaxError as e:
            pytest.fail(
                f"Generated Python for {name}.sr has syntax error: {e}\n"
                f"Generated code:\n{python_source}",
            )

        # Verify source mappings were generated
        assert source_mappings, f"Source mappings for {name}.sr should not be empty"


class TestV1MonolithicFeatures:
    """Test that V1 Monolithic agent uses expected DSL features correctly."""

    @pytest.fixture
    def v1_code(self, parser: ParserFactory) -> str:
        """Generate Python code for V1 Monolithic agent."""
        path = CODE_REVIEW_DIR / "v1-monolithic.sr"
        if not path.exists():
            pytest.skip("v1-monolithic.sr not found")

        source = path.read_text()
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "v1-monolithic.sr")
        return python_source

    def test_contains_parallel_execution(self, v1_code: str) -> None:
        """V1 should contain parallel agent execution code."""
        # Parallel blocks generate _parallel_specs and _execute_parallel_agents
        assert "_parallel_specs" in v1_code, (
            "V1 should use parallel do block (generates _parallel_specs)"
        )
        assert "_execute_parallel_agents" in v1_code, (
            "V1 should use parallel do block (generates _execute_parallel_agents)"
        )

    def test_contains_filter_comprehension(self, v1_code: str) -> None:
        """V1 should contain filter expression as list comprehension."""
        # Filter expressions generate [_item for _item in ... if ...]
        assert "[_item for _item in" in v1_code, (
            "V1 should use filter expression (generates list comprehension)"
        )
        assert "_item['confidence']" in v1_code, (
            "V1 should filter by confidence property"
        )

    def test_contains_property_assignment(self, v1_code: str) -> None:
        """V1 should contain property assignment code."""
        # Property assignments generate ctx.vars['obj']['prop'] = value
        # Looking for the pattern: $review.findings = $filtered
        assert "]['findings'] =" in v1_code or "['findings'] =" in v1_code, (
            "V1 should use property assignment for $review.findings"
        )


class TestV2ParallelFeatures:
    """Test that V2 Parallel agent uses expected DSL features correctly."""

    @pytest.fixture
    def v2_code(self, parser: ParserFactory) -> str:
        """Generate Python code for V2 Parallel agent."""
        path = CODE_REVIEW_DIR / "v2-parallel.sr"
        if not path.exists():
            pytest.skip("v2-parallel.sr not found")

        source = path.read_text()
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "v2-parallel.sr")
        return python_source

    def test_contains_parallel_execution(self, v2_code: str) -> None:
        """V2 should contain parallel agent execution code."""
        assert "_parallel_specs" in v2_code, (
            "V2 should use parallel do block (generates _parallel_specs)"
        )
        assert "_execute_parallel_agents" in v2_code, (
            "V2 should use parallel do block (generates _execute_parallel_agents)"
        )

    def test_contains_filter_comprehension(self, v2_code: str) -> None:
        """V2 should contain filter expression as list comprehension."""
        assert "[_item for _item in" in v2_code, (
            "V2 should use filter expression (generates list comprehension)"
        )

    def test_contains_list_concatenation(self, v2_code: str) -> None:
        """V2 should contain list concatenation using + operator."""
        # List concatenation generates (ctx.vars['a'] + ctx.vars['b'])
        # or (ctx.vars['a'] + ctx.vars['b']['prop'])
        # The V2 agent uses patterns like: $all_findings = $all_findings + $findings
        assert " + " in v2_code, (
            "V2 should use list concatenation (+ operator)"
        )


class TestV3HierarchicalFeatures:
    """Test that V3 Hierarchical agent uses expected DSL features correctly."""

    @pytest.fixture
    def v3_source(self) -> str:
        """Read V3 Hierarchical agent source."""
        path = CODE_REVIEW_DIR / "v3-hierarchical.sr"
        if not path.exists():
            pytest.skip("v3-hierarchical.sr not found")
        return path.read_text()

    @pytest.fixture
    def v3_code(self, parser: ParserFactory) -> str:
        """Generate Python code for V3 Hierarchical agent."""
        path = CODE_REVIEW_DIR / "v3-hierarchical.sr"
        if not path.exists():
            pytest.skip("v3-hierarchical.sr not found")

        source = path.read_text()
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "v3-hierarchical.sr")
        return python_source

    def test_contains_use_keyword(self, v3_source: str) -> None:
        """V3 source should contain 'use' keyword for sub-agents."""
        assert "use " in v3_source, (
            "V3 should use 'use' keyword for sub-agent delegation"
        )
        # Should delegate to multiple specialists
        assert "security_specialist" in v3_source
        assert "bug_specialist" in v3_source
        assert "quality_specialist" in v3_source

    def test_generates_sub_agents(self, v3_code: str) -> None:
        """V3 should generate code that references sub-agents."""
        # The use keyword should register sub-agents
        assert "'security_specialist'" in v3_code or "security_specialist" in v3_code
        assert "'bug_specialist'" in v3_code or "bug_specialist" in v3_code


class TestCodeReviewAgentsDslSourceFeatures:
    """Test that DSL source files contain expected syntax patterns."""

    def test_v1_source_contains_parallel_do(self) -> None:
        """V1 source should contain 'parallel do' syntax."""
        path = CODE_REVIEW_DIR / "v1-monolithic.sr"
        if not path.exists():
            pytest.skip("v1-monolithic.sr not found")

        source = path.read_text()
        assert "parallel do" in source, "V1 should contain 'parallel do' block"
        assert "end" in source, "V1 should have 'end' to close parallel block"

    def test_v1_source_contains_filter(self) -> None:
        """V1 source should contain 'filter ... where' syntax."""
        path = CODE_REVIEW_DIR / "v1-monolithic.sr"
        if not path.exists():
            pytest.skip("v1-monolithic.sr not found")

        source = path.read_text()
        assert "filter " in source, "V1 should contain 'filter' expression"
        assert " where " in source, "V1 should contain 'where' clause"
        assert ".confidence" in source, "V1 should filter by .confidence property"

    def test_v1_source_contains_property_assignment(self) -> None:
        """V1 source should contain property assignment syntax."""
        path = CODE_REVIEW_DIR / "v1-monolithic.sr"
        if not path.exists():
            pytest.skip("v1-monolithic.sr not found")

        source = path.read_text()
        # Pattern: $review.findings = $filtered
        assert "$review.findings = " in source, (
            "V1 should contain property assignment '$review.findings = ...'"
        )

    def test_v2_source_contains_parallel_do(self) -> None:
        """V2 source should contain 'parallel do' syntax."""
        path = CODE_REVIEW_DIR / "v2-parallel.sr"
        if not path.exists():
            pytest.skip("v2-parallel.sr not found")

        source = path.read_text()
        assert "parallel do" in source, "V2 should contain 'parallel do' block"

    def test_v2_source_contains_filter(self) -> None:
        """V2 source should contain 'filter ... where' syntax."""
        path = CODE_REVIEW_DIR / "v2-parallel.sr"
        if not path.exists():
            pytest.skip("v2-parallel.sr not found")

        source = path.read_text()
        assert "filter " in source, "V2 should contain 'filter' expression"
        assert " where " in source, "V2 should contain 'where' clause"

    def test_v2_source_contains_list_concatenation(self) -> None:
        """V2 source should contain list concatenation with + operator."""
        path = CODE_REVIEW_DIR / "v2-parallel.sr"
        if not path.exists():
            pytest.skip("v2-parallel.sr not found")

        source = path.read_text()
        # Pattern: $all_findings = $all_findings + $security_findings.findings
        assert " + $" in source or " + [" in source, (
            "V2 should use + operator for list concatenation"
        )

    def test_v3_source_contains_use_keyword(self) -> None:
        """V3 source should contain 'use' keyword for sub-agents."""
        path = CODE_REVIEW_DIR / "v3-hierarchical.sr"
        if not path.exists():
            pytest.skip("v3-hierarchical.sr not found")

        source = path.read_text()
        assert "use " in source, "V3 should contain 'use' keyword"
        # The use statement should list multiple sub-agents
        assert "context_builder" in source
        assert "validator" in source
        assert "synthesizer" in source


class TestCodeReviewAgentsCompileEnd2End:
    """End-to-end compilation test using the full compile_dsl function."""

    @pytest.mark.parametrize(
        ("name", "path", "features"),
        AGENT_FILES,
        ids=[name for name, _, _ in AGENT_FILES],
    )
    def test_full_compilation_pipeline(
        self,
        name: str,
        path: Path,
        features: list[str],  # noqa: ARG002
    ) -> None:
        """Test full compilation pipeline produces valid bytecode."""
        from streetrace.dsl.compiler import compile_dsl

        if not path.exists():
            pytest.skip(f"{name}.sr not found at {path}")

        source = path.read_text()

        try:
            bytecode, source_mappings = compile_dsl(
                source,
                f"{name}.sr",
                use_cache=False,  # Disable cache for test isolation
            )
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"Full compilation failed for {name}.sr: {e}")

        # Verify bytecode was produced
        assert bytecode is not None, f"Bytecode should not be None for {name}.sr"

        # Verify source mappings exist
        assert source_mappings, f"Source mappings should exist for {name}.sr"

        # Verify bytecode is executable (has correct type)
        assert hasattr(bytecode, "co_code"), (
            f"Bytecode should have co_code attribute for {name}.sr"
        )
