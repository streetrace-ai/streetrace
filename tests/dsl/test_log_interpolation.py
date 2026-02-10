"""Test log statement string interpolation.

Test that log statements with ${...} patterns generate proper f-string
expressions with variable and function call substitution.
"""

import pytest

from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar import ParserFactory


@pytest.fixture
def parser() -> ParserFactory:
    """Create DSL parser instance."""
    return ParserFactory.create()


class TestLogInterpolation:
    """Test log statement interpolation code generation."""

    def test_log_with_variable_interpolation(self, parser: ParserFactory) -> None:
        """Log with ${variable} generates f-string with ctx.vars access."""
        source = """
streetrace v1

flow main:
    count = 5
    log "Found ${count} items"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        assert 'ctx.log(f"Found {ctx.vars[\'count\']} items")' in python_source

    def test_log_with_len_function(self, parser: ParserFactory) -> None:
        """Log with ${len(var)} generates f-string with len() call."""
        source = """
streetrace v1

flow main:
    items = []
    log "Total items: ${len(items)}"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        assert 'ctx.log(f"Total items: {len(ctx.vars[\'items\'])}")' in python_source

    def test_log_with_property_access(self, parser: ParserFactory) -> None:
        """Log with ${obj.prop} generates f-string with dict access."""
        source = """
streetrace v1

flow main:
    chunk = {}
    log "Processing: ${chunk.title}"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        assert (
            'ctx.log(f"Processing: {ctx.vars[\'chunk\'][\'title\']}")'
            in python_source
        )

    def test_log_with_multiple_interpolations(self, parser: ParserFactory) -> None:
        """Log with multiple ${...} patterns generates proper f-string."""
        source = """
streetrace v1

flow main:
    index = 1
    total = 10
    log "Processing ${index}/${total}"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        expected = (
            "ctx.log(f\"Processing {ctx.vars['index']}/{ctx.vars['total']}\")"
        )
        assert expected in python_source

    def test_log_without_interpolation_unchanged(self, parser: ParserFactory) -> None:
        """Log without ${...} generates simple string literal."""
        source = """
streetrace v1

flow main:
    log "Simple message"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        assert 'ctx.log("Simple message")' in python_source
        # Should NOT be an f-string
        assert 'ctx.log(f"Simple message")' not in python_source

    def test_notify_with_interpolation(self, parser: ParserFactory) -> None:
        """Notify statements also support interpolation."""
        source = """
streetrace v1

flow main:
    status = "done"
    notify "Status: ${status}"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        assert 'ctx.notify(f"Status: {ctx.vars[\'status\']}")' in python_source

    def test_log_with_len_and_property(self, parser: ParserFactory) -> None:
        """Log with ${len(obj.prop)} generates proper nested access."""
        source = """
streetrace v1

flow main:
    findings = []
    log "Security findings: ${len(security_findings)}"
"""
        tree = parser.parse(source)
        ast = transform(tree)
        generator = CodeGenerator()
        python_source, _ = generator.generate(ast, "test.sr")

        expected = (
            'ctx.log(f"Security findings: '
            "{len(ctx.vars['security_findings'])}\")"
        )
        assert expected in python_source
