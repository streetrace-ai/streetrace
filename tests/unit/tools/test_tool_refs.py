"""Tests for ToolRef system."""

import pytest
from pydantic import ValidationError

from streetrace.tools.mcp_transport import HttpTransport, StdioTransport
from streetrace.tools.tool_refs import (
    CallableToolRef,
    McpToolRef,
    StreetraceToolRef,
)


class TestMcpToolRef:
    """Test McpToolRef class."""

    def test_creation_with_inline_transport(self) -> None:
        """Test creating McpToolRef with inline transport."""
        transport = HttpTransport(url="http://localhost:8000/mcp")
        tool_ref = McpToolRef(
            server=transport,
            tools=["*"],
        )

        assert tool_ref.kind == "mcp"
        assert isinstance(tool_ref.server, HttpTransport)
        assert tool_ref.server.url == "http://localhost:8000/mcp"
        assert tool_ref.tools == ["*"]

    def test_model_validation(self) -> None:
        """Test Pydantic model validation."""
        data = {
            "kind": "mcp",
            "server": {
                "type": "stdio",
                "command": "filesystem",
                "args": ["fake_server"],
            },
            "tools": ["tool1", "tool2"],
        }
        tool_ref = McpToolRef.model_validate(data)

        assert tool_ref.server.type == "stdio"
        assert tool_ref.server.command == "filesystem"
        assert tool_ref.tools == ["tool1", "tool2"]


class TestStreetraceToolRef:
    """Test StreetraceToolRef class."""

    def test_creation(self) -> None:
        """Test creating StreetraceToolRef."""
        tool_ref = StreetraceToolRef(
            module="fs",
            function="list_files",
        )

        assert tool_ref.kind == "streetrace"
        assert tool_ref.module == "fs"
        assert tool_ref.function == "list_files"

    def test_creation_minimal(self) -> None:
        """Test creating minimal StreetraceToolRef."""
        tool_ref = StreetraceToolRef(module="cli", function="run_command")

        assert tool_ref.kind == "streetrace"
        assert tool_ref.module == "cli"
        assert tool_ref.function == "run_command"

    def test_model_validation(self) -> None:
        """Test Pydantic model validation."""
        data = {
            "kind": "streetrace",
            "module": "fs_tool",
            "function": "write_file",
        }
        tool_ref = StreetraceToolRef.model_validate(data)

        assert tool_ref.module == "fs_tool"
        assert tool_ref.function == "write_file"

    def test_validation_missing_fields(self) -> None:
        """Test validation fails with missing required fields."""
        with pytest.raises(ValidationError):
            StreetraceToolRef.model_validate({"kind": "streetrace", "module": "fs"})


class TestCallableToolRef:
    """Test CallableToolRef class."""

    def test_creation(self) -> None:
        """Test creating CallableToolRef."""
        tool_ref = CallableToolRef(
            import_path="mypackage.tools:my_function",
        )

        assert tool_ref.kind == "callable"
        assert tool_ref.import_path == "mypackage.tools:my_function"

    def test_creation_minimal(self) -> None:
        """Test creating minimal CallableToolRef."""
        tool_ref = CallableToolRef(import_path="utils:helper")

        assert tool_ref.kind == "callable"
        assert tool_ref.import_path == "utils:helper"

    def test_model_validation(self) -> None:
        """Test Pydantic model validation."""
        data = {
            "kind": "callable",
            "import_path": "mylib.functions:process_data",
        }
        tool_ref = CallableToolRef.model_validate(data)

        assert tool_ref.import_path == "mylib.functions:process_data"


class TestToolRefIntegration:
    """Test ToolRef integration scenarios."""

    def test_mixed_tool_refs(self) -> None:
        """Test creating various tool reference types."""
        mcp_ref = McpToolRef(
            server=StdioTransport(command="filesystem", args=["fake_server"]),
            tools=["list"],
        )
        streetrace_ref = StreetraceToolRef(module="cli", function="run")
        callable_ref = CallableToolRef(import_path="utils:helper")

        tool_refs = [mcp_ref, streetrace_ref, callable_ref]

        assert len(tool_refs) == 3
        assert all(hasattr(ref, "kind") for ref in tool_refs)
        assert {ref.kind for ref in tool_refs} == {"mcp", "streetrace", "callable"}
