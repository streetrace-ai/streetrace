"""Tests for DSL example files in agents/examples/dsl/.

Validate that all example files in the examples directory:
1. Parse correctly
2. Pass semantic validation
3. Generate valid Python code without warnings
"""

from pathlib import Path

import pytest

from streetrace.dsl import validate_dsl
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory

# Get the examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "agents" / "examples" / "dsl"


def get_example_files() -> list[tuple[str, Path]]:
    """Get all .sr files from the examples directory.

    Returns:
        List of tuples (filename, path) for each example file.

    """
    if not EXAMPLES_DIR.exists():
        return []
    return [(f.stem, f) for f in sorted(EXAMPLES_DIR.glob("*.sr"))]


EXAMPLE_FILES = get_example_files()


class TestExampleFilesParsing:
    """Test that all example files parse correctly."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    @pytest.mark.parametrize(
        ("name", "path"),
        EXAMPLE_FILES,
        ids=[name for name, _ in EXAMPLE_FILES],
    )
    def test_example_file_parses(
        self, name: str, path: Path, parser: ParserFactory,
    ) -> None:
        """Example files should parse without errors."""
        source = path.read_text()
        tree = parser.parse(source)
        assert tree is not None, f"Failed to parse {name}.sr"
        assert tree.data == "start", f"Parse tree root should be 'start' for {name}.sr"


class TestExampleFilesValidation:
    """Test that all example files pass semantic validation."""

    @pytest.mark.parametrize(
        ("name", "path"),
        EXAMPLE_FILES,
        ids=[name for name, _ in EXAMPLE_FILES],
    )
    def test_example_file_validates(self, name: str, path: Path) -> None:
        """Example files should pass semantic validation without errors."""
        source = path.read_text()
        diagnostics = validate_dsl(source, f"{name}.sr")
        errors = [d for d in diagnostics if d.severity.name.lower() == "error"]

        assert not errors, (
            f"Example '{name}.sr' has semantic errors: "
            f"{[e.message for e in errors]}"
        )


class TestExampleFilesCodeGeneration:
    """Test that all example files generate valid Python code."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    @pytest.mark.parametrize(
        ("name", "path"),
        EXAMPLE_FILES,
        ids=[name for name, _ in EXAMPLE_FILES],
    )
    def test_example_file_generates_python(
        self, name: str, path: Path, parser: ParserFactory,
    ) -> None:
        """Example files should generate valid Python code."""
        source = path.read_text()

        # Parse and transform
        tree = parser.parse(source)
        ast = transform(tree)

        # Generate code
        generator = CodeGenerator()
        python_source, source_mappings = generator.generate(ast, f"{name}.sr")

        # Verify Python code is non-empty
        assert python_source, f"Generated Python for {name}.sr should not be empty"

        # Verify Python code compiles without syntax errors
        try:
            compile(python_source, f"<dsl:{name}.sr>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated Python for {name}.sr has syntax error: {e}")

        # Verify source mappings were generated
        assert source_mappings, f"Source mappings for {name}.sr should not be empty"


PLACEHOLDER_PHRASES = (
    "simplified for now",
    "not yet implemented",
    "placeholder",
    "TODO",
    "FIXME",
)


class TestExampleFilesNoPlaceholders:
    """Test that example files don't contain placeholder comments."""

    @pytest.mark.parametrize(
        ("name", "path"),
        EXAMPLE_FILES,
        ids=[name for name, _ in EXAMPLE_FILES],
    )
    def test_example_file_no_placeholders(self, name: str, path: Path) -> None:
        """Example files should not contain placeholder comments."""
        source = path.read_text()
        lines = source.split("\n")

        violations = []
        for i, line in enumerate(lines, start=1):
            # Check for placeholder phrases in comments
            if "#" in line:
                comment = line.split("#", 1)[1].lower()
                for phrase in PLACEHOLDER_PHRASES:
                    if phrase.lower() in comment:
                        msg = f"Line {i}: contains '{phrase}' - {line.strip()}"
                        violations.append(msg)

        assert not violations, (
            f"Example '{name}.sr' contains placeholder comments:\n"
            + "\n".join(violations)
        )


class TestExampleFilesDemonstrateFeatures:
    """Test that example files demonstrate their advertised features."""

    def test_match_sr_demonstrates_pattern_matching(self) -> None:
        """match.sr should demonstrate pattern matching with match statement."""
        path = EXAMPLES_DIR / "match.sr"
        if not path.exists():
            pytest.skip("match.sr not found")

        source = path.read_text()

        # Should contain match statement
        assert "match " in source, "match.sr should contain 'match' statement"
        assert "when " in source, "match.sr should contain 'when' clauses"

    def test_flow_sr_demonstrates_flow_execution(self) -> None:
        """flow.sr should demonstrate flow with agent execution."""
        path = EXAMPLES_DIR / "flow.sr"
        if not path.exists():
            pytest.skip("flow.sr not found")

        source = path.read_text()

        # Should contain flow definition
        assert "flow " in source, "flow.sr should contain 'flow' definition"
        assert "run agent " in source, "flow.sr should contain 'run agent'"
        assert "$input_prompt" in source, "flow.sr should use $input_prompt"

    def test_parallel_sr_demonstrates_parallel_execution(self) -> None:
        """parallel.sr should demonstrate parallel execution."""
        path = EXAMPLES_DIR / "parallel.sr"
        if not path.exists():
            pytest.skip("parallel.sr not found")

        source = path.read_text()

        # Should contain parallel block
        assert "parallel do" in source, "parallel.sr should contain 'parallel do' block"

    def test_handlers_sr_demonstrates_event_handlers(self) -> None:
        """handlers.sr should demonstrate event handlers."""
        path = EXAMPLES_DIR / "handlers.sr"
        if not path.exists():
            pytest.skip("handlers.sr not found")

        source = path.read_text()

        # Should contain event handlers
        assert "on input do" in source, "handlers.sr should contain 'on input do'"
        assert "on output do" in source, "handlers.sr should contain 'on output do'"

    def test_schema_sr_demonstrates_schemas(self) -> None:
        """schema.sr should demonstrate schema definitions."""
        path = EXAMPLES_DIR / "schema.sr"
        if not path.exists():
            pytest.skip("schema.sr not found")

        source = path.read_text()

        # Should contain schema definitions
        assert "schema " in source, "schema.sr should contain schema definitions"
        assert "expecting " in source, "schema.sr should use 'expecting' in prompts"

    def test_policies_sr_demonstrates_policies(self) -> None:
        """policies.sr should demonstrate retry and timeout policies."""
        path = EXAMPLES_DIR / "policies.sr"
        if not path.exists():
            pytest.skip("policies.sr not found")

        source = path.read_text()

        # Should contain retry and timeout policies
        assert "retry " in source, "policies.sr should contain retry policies"
        assert "timeout " in source, "policies.sr should contain timeout policies"
