"""Test CompactCommand behavior when no history is available.

This module tests how CompactCommand handles scenarios where there is no current session
or the session has no events to compact.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.sessions import Session

from streetrace.args import Args
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.llm.model_factory import ModelFactory
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus


class TestCompactCommandNoHistory:
    """Test CompactCommand behavior when no history is available."""

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

    @pytest.mark.asyncio
    async def test_no_current_session(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
    ) -> None:
        """Test behavior when session_manager returns no current session."""
        # Arrange
        mock_dependencies["session_manager"].get_current_session = AsyncMock(
            return_value=None,
        )

        # Act
        await compact_command.execute_async()

        # Assert
        mock_dependencies["session_manager"].get_current_session.assert_called_once()
        mock_dependencies["ui_bus"].dispatch_ui_update.assert_called_once()

        # Verify the UI event is an Info message about no history
        call_args = mock_dependencies["ui_bus"].dispatch_ui_update.call_args[0][0]
        assert isinstance(call_args, ui_events.Info)
        assert "no history available to compact" in call_args.lower()

        # Verify no other session operations were called
        assert (
            not hasattr(
                mock_dependencies["session_manager"],
                "replace_current_session_events",
            )
            or not mock_dependencies[
                "session_manager"
            ].replace_current_session_events.called
        )

    @pytest.mark.asyncio
    async def test_session_with_no_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
    ) -> None:
        """Test behavior when current session exists but has no events."""
        # Arrange
        empty_session = Mock(spec=Session)
        empty_session.events = []
        mock_dependencies[
            "session_manager"
        ].get_current_session.return_value = empty_session

        # Act
        await compact_command.execute_async()

        # Assert
        mock_dependencies["session_manager"].get_current_session.assert_called_once()
        mock_dependencies["ui_bus"].dispatch_ui_update.assert_called_once()

        # Verify the UI event is an Info message about no history
        call_args = mock_dependencies["ui_bus"].dispatch_ui_update.call_args[0][0]
        assert isinstance(call_args, ui_events.Info)
        assert "no history available to compact" in call_args.lower()

        # Verify no session replacement occurred
        assert (
            not hasattr(
                mock_dependencies["session_manager"],
                "replace_current_session_events",
            )
            or not mock_dependencies[
                "session_manager"
            ].replace_current_session_events.called
        )

    @pytest.mark.asyncio
    async def test_session_with_none_events(
        self,
        compact_command: CompactCommand,
        mock_dependencies: dict[str, Mock],
    ) -> None:
        """Test behavior when current session has None as events."""
        # Arrange
        session_with_none_events = Mock(spec=Session)
        session_with_none_events.events = None
        mock_dependencies[
            "session_manager"
        ].get_current_session.return_value = session_with_none_events

        # Act
        await compact_command.execute_async()

        # Assert
        mock_dependencies["session_manager"].get_current_session.assert_called_once()
        mock_dependencies["ui_bus"].dispatch_ui_update.assert_called_once()

        # Verify the UI event is an Info message about no history
        call_args = mock_dependencies["ui_bus"].dispatch_ui_update.call_args[0][0]
        assert isinstance(call_args, ui_events.Info)
        assert "no history available to compact" in call_args.lower()
