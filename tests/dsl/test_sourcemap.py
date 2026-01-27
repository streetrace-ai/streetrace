"""Tests for source map system.

Test the source mapping classes used to translate generated Python
line numbers back to original DSL file locations.
"""

from streetrace.dsl.sourcemap.registry import SourceMapping, SourceMapRegistry

# =============================================================================
# SourceMapping Tests
# =============================================================================


class TestSourceMapping:
    """Test SourceMapping dataclass."""

    def test_create_minimal_mapping(self) -> None:
        """Create a mapping with required fields only."""
        mapping = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="my_agent.sr",
            source_line=5,
            source_column=4,
        )
        assert mapping.generated_line == 10
        assert mapping.generated_column == 0
        assert mapping.source_file == "my_agent.sr"
        assert mapping.source_line == 5
        assert mapping.source_column == 4
        assert mapping.source_end_line is None
        assert mapping.source_end_column is None

    def test_create_mapping_with_end_positions(self) -> None:
        """Create a mapping with end positions for multi-line spans."""
        mapping = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="my_agent.sr",
            source_line=5,
            source_column=4,
            source_end_line=7,
            source_end_column=20,
        )
        assert mapping.source_end_line == 7
        assert mapping.source_end_column == 20

    def test_mapping_equality(self) -> None:
        """Two mappings with same values should be equal."""
        mapping1 = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="test.sr",
            source_line=5,
            source_column=4,
        )
        mapping2 = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="test.sr",
            source_line=5,
            source_column=4,
        )
        assert mapping1 == mapping2

    def test_mapping_inequality(self) -> None:
        """Mappings with different values should not be equal."""
        mapping1 = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="test.sr",
            source_line=5,
            source_column=4,
        )
        mapping2 = SourceMapping(
            generated_line=11,
            generated_column=0,
            source_file="test.sr",
            source_line=5,
            source_column=4,
        )
        assert mapping1 != mapping2


# =============================================================================
# SourceMapRegistry Tests
# =============================================================================


class TestSourceMapRegistry:
    """Test SourceMapRegistry class."""

    def test_create_empty_registry(self) -> None:
        """Create an empty registry."""
        registry = SourceMapRegistry()
        assert registry.lookup("<generated:test.sr>", 10) is None

    def test_add_single_mapping(self) -> None:
        """Add a single mapping and retrieve it."""
        registry = SourceMapRegistry()
        mapping = SourceMapping(
            generated_line=10,
            generated_column=0,
            source_file="my_agent.sr",
            source_line=5,
            source_column=4,
        )
        registry.add_mapping("<generated:my_agent.sr>", mapping)

        result = registry.lookup("<generated:my_agent.sr>", 10)
        assert result is not None
        assert result.source_line == 5
        assert result.source_file == "my_agent.sr"

    def test_add_multiple_mappings(self) -> None:
        """Add multiple mappings for the same file."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=15,
                generated_column=0,
                source_file="test.sr",
                source_line=8,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=20,
                generated_column=0,
                source_file="test.sr",
                source_line=12,
                source_column=0,
            ),
        )

        # Lookup exact matches
        result = registry.lookup("<generated:test.sr>", 10)
        assert result is not None
        assert result.source_line == 5

        result = registry.lookup("<generated:test.sr>", 15)
        assert result is not None
        assert result.source_line == 8

        result = registry.lookup("<generated:test.sr>", 20)
        assert result is not None
        assert result.source_line == 12

    def test_lookup_line_between_mappings(self) -> None:
        """Lookup a line that falls between mapped lines."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=20,
                generated_column=0,
                source_file="test.sr",
                source_line=10,
                source_column=0,
            ),
        )

        # Line 15 should map to the previous mapping (line 10 -> source 5)
        result = registry.lookup("<generated:test.sr>", 15)
        assert result is not None
        assert result.source_line == 5

    def test_lookup_line_before_first_mapping(self) -> None:
        """Lookup a line before the first mapping."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )

        # Line 5 is before the first mapping, should return None
        result = registry.lookup("<generated:test.sr>", 5)
        assert result is None

    def test_lookup_different_files(self) -> None:
        """Lookup mappings from different generated files."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:file1.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="file1.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:file2.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="file2.sr",
                source_line=15,
                source_column=0,
            ),
        )

        result1 = registry.lookup("<generated:file1.sr>", 10)
        assert result1 is not None
        assert result1.source_file == "file1.sr"

        result2 = registry.lookup("<generated:file2.sr>", 10)
        assert result2 is not None
        assert result2.source_file == "file2.sr"

    def test_lookup_nonexistent_file(self) -> None:
        """Lookup from a file that has no mappings."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )

        result = registry.lookup("<generated:other.sr>", 10)
        assert result is None

    def test_get_all_mappings_for_file(self) -> None:
        """Get all mappings for a specific generated file."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=20,
                generated_column=0,
                source_file="test.sr",
                source_line=10,
                source_column=0,
            ),
        )

        mappings = registry.get_mappings("<generated:test.sr>")
        assert len(mappings) == 2
        assert mappings[0].generated_line == 10
        assert mappings[1].generated_line == 20

    def test_get_mappings_for_nonexistent_file(self) -> None:
        """Get mappings for a file with no mappings returns empty list."""
        registry = SourceMapRegistry()

        mappings = registry.get_mappings("<generated:nonexistent.sr>")
        assert mappings == []


# =============================================================================
# Line Number Translation Tests
# =============================================================================


class TestLineNumberTranslation:
    """Test line number translation scenarios."""

    def test_exact_line_translation(self) -> None:
        """Translate an exact line match."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:agent.sr>",
            SourceMapping(
                generated_line=42,
                generated_column=0,
                source_file="agent.sr",
                source_line=15,
                source_column=4,
            ),
        )

        result = registry.lookup("<generated:agent.sr>", 42)
        assert result is not None
        assert result.source_line == 15
        assert result.source_column == 4

    def test_translation_preserves_file_info(self) -> None:
        """Translation preserves source file information."""
        registry = SourceMapRegistry()

        registry.add_mapping(
            "<generated:workflow.sr>",
            SourceMapping(
                generated_line=100,
                generated_column=0,
                source_file="./agents/workflow.sr",
                source_line=25,
                source_column=0,
            ),
        )

        result = registry.lookup("<generated:workflow.sr>", 100)
        assert result is not None
        assert result.source_file == "./agents/workflow.sr"

    def test_multiple_statements_same_source_line(self) -> None:
        """Multiple generated lines can map to the same source line."""
        registry = SourceMapRegistry()

        # Generated code might expand a single DSL line into multiple Python lines
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=10,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=11,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )
        registry.add_mapping(
            "<generated:test.sr>",
            SourceMapping(
                generated_line=12,
                generated_column=0,
                source_file="test.sr",
                source_line=5,
                source_column=0,
            ),
        )

        # All three lines should map back to source line 5
        for gen_line in [10, 11, 12]:
            result = registry.lookup("<generated:test.sr>", gen_line)
            assert result is not None
            assert result.source_line == 5
