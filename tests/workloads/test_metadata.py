"""Tests for WorkloadMetadata dataclass."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Literal

import pytest

from streetrace.workloads.metadata import WorkloadMetadata


class TestWorkloadMetadataImmutability:
    """Test that WorkloadMetadata is frozen (immutable)."""

    def test_cannot_modify_name_after_creation(self) -> None:
        """Test that name attribute cannot be changed after creation."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        with pytest.raises(FrozenInstanceError):
            metadata.name = "modified-name"  # type: ignore[misc]

    def test_cannot_modify_description_after_creation(self) -> None:
        """Test that description attribute cannot be changed after creation."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        with pytest.raises(FrozenInstanceError):
            metadata.description = "modified description"  # type: ignore[misc]

    def test_cannot_modify_source_path_after_creation(self) -> None:
        """Test that source_path attribute cannot be changed after creation."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        with pytest.raises(FrozenInstanceError):
            metadata.source_path = Path("/other/path.sr")  # type: ignore[misc]

    def test_cannot_modify_format_after_creation(self) -> None:
        """Test that format attribute cannot be changed after creation."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        with pytest.raises(FrozenInstanceError):
            metadata.format = "yaml"  # type: ignore[misc]


class TestWorkloadMetadataEquality:
    """Test WorkloadMetadata equality based on fields."""

    def test_equal_metadata_are_equal(self) -> None:
        """Test that two metadata with same fields are equal."""
        metadata1 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        assert metadata1 == metadata2

    def test_different_name_not_equal(self) -> None:
        """Test that metadata with different names are not equal."""
        metadata1 = WorkloadMetadata(
            name="workload-a",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="workload-b",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        assert metadata1 != metadata2

    def test_different_description_not_equal(self) -> None:
        """Test that metadata with different descriptions are not equal."""
        metadata1 = WorkloadMetadata(
            name="test-workload",
            description="Description A",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="test-workload",
            description="Description B",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        assert metadata1 != metadata2

    def test_different_source_path_not_equal(self) -> None:
        """Test that metadata with different source paths are not equal."""
        metadata1 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/path/a.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/path/b.sr"),
            format="dsl",
        )

        assert metadata1 != metadata2

    def test_different_format_not_equal(self) -> None:
        """Test that metadata with different formats are not equal."""
        metadata1 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.yaml"),
            format="yaml",
        )

        assert metadata1 != metadata2

    def test_hash_consistent_with_equality(self) -> None:
        """Test that equal metadata have the same hash."""
        metadata1 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )
        metadata2 = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        assert hash(metadata1) == hash(metadata2)

    def test_can_use_as_dict_key(self) -> None:
        """Test that metadata can be used as a dictionary key."""
        metadata = WorkloadMetadata(
            name="test-workload",
            description="A test workload",
            source_path=Path("/test/path.sr"),
            format="dsl",
        )

        # Should not raise - frozen dataclass is hashable
        test_dict: dict[WorkloadMetadata, str] = {metadata: "value"}
        assert test_dict[metadata] == "value"


class TestWorkloadMetadataFormatValues:
    """Test WorkloadMetadata with all format literal values."""

    def test_dsl_format(self) -> None:
        """Test metadata with dsl format."""
        metadata = WorkloadMetadata(
            name="dsl-workload",
            description="A DSL workload",
            source_path=Path("/test/agent.sr"),
            format="dsl",
        )

        assert metadata.format == "dsl"
        assert metadata.name == "dsl-workload"
        assert metadata.description == "A DSL workload"
        assert metadata.source_path == Path("/test/agent.sr")

    def test_yaml_format(self) -> None:
        """Test metadata with yaml format."""
        metadata = WorkloadMetadata(
            name="yaml-workload",
            description="A YAML workload",
            source_path=Path("/test/agent.yaml"),
            format="yaml",
        )

        assert metadata.format == "yaml"
        assert metadata.name == "yaml-workload"
        assert metadata.description == "A YAML workload"
        assert metadata.source_path == Path("/test/agent.yaml")

    def test_python_format(self) -> None:
        """Test metadata with python format."""
        metadata = WorkloadMetadata(
            name="python-workload",
            description="A Python workload",
            source_path=Path("/test/agent/__init__.py"),
            format="python",
        )

        assert metadata.format == "python"
        assert metadata.name == "python-workload"
        assert metadata.description == "A Python workload"
        assert metadata.source_path == Path("/test/agent/__init__.py")

    def test_format_type_annotation(self) -> None:
        """Test that format field uses proper Literal type."""
        # This test verifies the type annotation at runtime
        metadata = WorkloadMetadata(
            name="test",
            description="test",
            source_path=Path("/test"),
            format="dsl",
        )

        # Verify the format is one of the expected values
        valid_formats: set[Literal["dsl", "yaml", "python"]] = {"dsl", "yaml", "python"}
        assert metadata.format in valid_formats


class TestWorkloadMetadataCreation:
    """Test WorkloadMetadata creation scenarios."""

    def test_create_with_all_fields(self) -> None:
        """Test creating metadata with all required fields."""
        metadata = WorkloadMetadata(
            name="complete-workload",
            description="A complete test workload",
            source_path=Path("/full/path/to/workload.sr"),
            format="dsl",
        )

        assert metadata.name == "complete-workload"
        assert metadata.description == "A complete test workload"
        assert metadata.source_path == Path("/full/path/to/workload.sr")
        assert metadata.format == "dsl"

    def test_create_with_empty_description(self) -> None:
        """Test creating metadata with empty description."""
        metadata = WorkloadMetadata(
            name="minimal",
            description="",
            source_path=Path("/test.sr"),
            format="dsl",
        )

        assert metadata.description == ""

    def test_create_with_relative_path(self) -> None:
        """Test creating metadata with relative source path."""
        metadata = WorkloadMetadata(
            name="relative",
            description="Workload with relative path",
            source_path=Path("agents/my_agent.sr"),
            format="dsl",
        )

        assert metadata.source_path == Path("agents/my_agent.sr")
        assert not metadata.source_path.is_absolute()

    def test_create_with_absolute_path(self) -> None:
        """Test creating metadata with absolute source path."""
        metadata = WorkloadMetadata(
            name="absolute",
            description="Workload with absolute path",
            source_path=Path("/home/user/agents/my_agent.sr"),
            format="dsl",
        )

        assert metadata.source_path == Path("/home/user/agents/my_agent.sr")
        assert metadata.source_path.is_absolute()
