"""Test CompactCommand basic properties and initialization.

This module tests the fundamental aspects of the CompactCommand class including
property methods, command metadata, and proper initialization.
"""

from unittest.mock import Mock

import pytest

from streetrace.args import Args
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.llm.model_factory import ModelFactory
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui.ui_bus import UiBus


class TestCompactCommandProperties:
    """Test CompactCommand basic properties and metadata."""

    @pytest.fixture
    def mock_dependencies(self) -> dict[str, Mock]:
        """Create mock dependencies for CompactCommand."""
        return {
            "ui_bus": Mock(spec=UiBus),
            "args": Mock(spec=Args),
            "session_manager": Mock(spec=SessionManager),
            "system_context": Mock(spec=SystemContext),
            "model_factory": Mock(spec=ModelFactory),
        }

    @pytest.fixture
    def compact_command(self, mock_dependencies: dict[str, Mock]) -> CompactCommand:
        """Create a CompactCommand instance with mocked dependencies."""
        return CompactCommand(**mock_dependencies)

    def test_command_names(self, compact_command: CompactCommand) -> None:
        """Test that command returns correct invocation names."""
        names = compact_command.names

        assert isinstance(names, list)
        assert len(names) == 1
        assert names[0] == "compact"

    def test_command_description(self, compact_command: CompactCommand) -> None:
        """Test that command returns meaningful description."""
        description = compact_command.description

        assert isinstance(description, str)
        assert len(description.strip()) > 0
        assert "summarize" in description.lower() or "compact" in description.lower()
        assert "history" in description.lower()

    def test_initialization_stores_dependencies(
        self,
        mock_dependencies: dict[str, Mock],
    ) -> None:
        """Test that command properly stores all injected dependencies."""
        command = CompactCommand(**mock_dependencies)

        assert command.ui_bus is mock_dependencies["ui_bus"]
        assert command.args is mock_dependencies["args"]
        assert command.session_manager is mock_dependencies["session_manager"]
        assert command.system_context is mock_dependencies["system_context"]
        assert command.model_factory is mock_dependencies["model_factory"]

    def test_inherits_from_command_base(self, compact_command: CompactCommand) -> None:
        """Test that CompactCommand properly inherits from Command base class."""
        from streetrace.commands.base_command import Command

        assert isinstance(compact_command, Command)
        # Verify it implements required abstract methods
        assert hasattr(compact_command, "names")
        assert hasattr(compact_command, "description")
        assert hasattr(compact_command, "execute_async")
        assert callable(compact_command.execute_async)
