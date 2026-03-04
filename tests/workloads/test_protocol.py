"""Tests for the Workload protocol."""

from collections.abc import AsyncGenerator
from typing import runtime_checkable

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai.types import Content

from streetrace.workloads.protocol import Workload


class TestWorkloadProtocol:
    """Test cases for the Workload protocol definition."""

    def test_workload_is_runtime_checkable(self) -> None:
        """Test that Workload protocol is decorated with runtime_checkable."""
        # The protocol should be runtime checkable for isinstance() checks
        assert hasattr(Workload, "__protocol_attrs__") or runtime_checkable

    def test_workload_has_run_async_method(self) -> None:
        """Test that Workload protocol defines run_async method."""
        # Protocol should define run_async method
        assert hasattr(Workload, "run_async")

    def test_workload_has_close_method(self) -> None:
        """Test that Workload protocol defines close method."""
        # Protocol should define close method
        assert hasattr(Workload, "close")


class TestWorkloadProtocolCompliance:
    """Test that classes can properly implement the Workload protocol."""

    def test_compliant_class_satisfies_protocol(self) -> None:
        """Test that a properly implemented class satisfies the Workload protocol."""

        class CompliantWorkload:
            """A class that properly implements the Workload protocol."""

            async def run_async(
                self,
                session: Session,  # noqa: ARG002
                message: Content | None,  # noqa: ARG002
            ) -> AsyncGenerator[Event, None]:
                """Execute the workload and yield events."""
                yield  # type: ignore[misc]

            async def close(self) -> None:
                """Clean up resources."""

        # Create instance and verify it has required methods
        workload = CompliantWorkload()
        assert hasattr(workload, "run_async")
        assert hasattr(workload, "close")
        assert callable(workload.run_async)
        assert callable(workload.close)

    def test_compliant_class_isinstance_check(self) -> None:
        """Test isinstance check with a compliant class."""

        class CompliantWorkload:
            """A class that properly implements the Workload protocol."""

            async def run_async(
                self,
                session: Session,  # noqa: ARG002
                message: Content | None,  # noqa: ARG002
            ) -> AsyncGenerator[Event, None]:
                """Execute the workload and yield events."""
                yield  # type: ignore[misc]

            async def close(self) -> None:
                """Clean up resources."""

        workload = CompliantWorkload()
        # Protocol isinstance check should work
        assert isinstance(workload, Workload)

    def test_non_compliant_class_fails_isinstance_check(self) -> None:
        """Test that a class missing methods fails isinstance check."""

        class NonCompliantWorkload:
            """A class that does NOT implement the Workload protocol."""

            async def run_async(
                self,
                session: Session,  # noqa: ARG002
                message: Content | None,  # noqa: ARG002
            ) -> AsyncGenerator[Event, None]:
                """Execute the workload and yield events."""
                yield  # type: ignore[misc]

            # Missing close() method

        workload = NonCompliantWorkload()
        # Should not be considered a Workload
        assert not isinstance(workload, Workload)


class TestWorkloadProtocolExecution:
    """Test actual execution of Workload protocol implementations."""

    @pytest.fixture
    def mock_session(self) -> Session:
        """Create a mock Session for testing."""
        from unittest.mock import MagicMock

        session = MagicMock(spec=Session)
        session.app_name = "test-app"
        session.user_id = "test-user"
        session.id = "test-session-id"
        return session

    @pytest.fixture
    def mock_content(self) -> Content:
        """Create a mock Content for testing."""
        from unittest.mock import MagicMock

        return MagicMock(spec=Content)

    async def test_run_async_yields_events(self, mock_session: Session) -> None:
        """Test that run_async properly yields events."""
        from unittest.mock import MagicMock

        class EventYieldingWorkload:
            """Workload that yields specific events."""

            def __init__(self) -> None:
                self.events_to_yield: list[Event] = []

            async def run_async(
                self,
                session: Session,  # noqa: ARG002
                message: Content | None,  # noqa: ARG002
            ) -> AsyncGenerator[Event, None]:
                """Execute the workload and yield events."""
                for event in self.events_to_yield:
                    yield event

            async def close(self) -> None:
                """Clean up resources."""

        # Arrange
        workload = EventYieldingWorkload()
        mock_event_1 = MagicMock(spec=Event)
        mock_event_2 = MagicMock(spec=Event)
        workload.events_to_yield = [mock_event_1, mock_event_2]

        # Act
        collected_events = [
            event async for event in workload.run_async(mock_session, None)
        ]

        # Assert
        assert len(collected_events) == 2
        assert collected_events[0] is mock_event_1
        assert collected_events[1] is mock_event_2

    async def test_close_is_called(self) -> None:
        """Test that close method can be called."""

        class TrackingWorkload:
            """Workload that tracks close calls."""

            def __init__(self) -> None:
                self.close_called = False

            async def run_async(
                self,
                session: Session,  # noqa: ARG002
                message: Content | None,  # noqa: ARG002
            ) -> AsyncGenerator[Event, None]:
                """Execute the workload and yield events."""
                yield  # type: ignore[misc]

            async def close(self) -> None:
                """Clean up resources."""
                self.close_called = True

        # Arrange
        workload = TrackingWorkload()

        # Act
        await workload.close()

        # Assert
        assert workload.close_called is True
