"""Test Supervisor initialization and basic properties.

This module tests the fundamental aspects of the Supervisor class including
property methods, command metadata, and proper initialization.
"""

from streetrace.workflow.supervisor import Supervisor


class TestSupervisorInitialization:
    """Test Supervisor initialization and basic setup."""

    def test_initialization_stores_dependencies(
        self,
        mock_agent_manager,
        mock_session_manager,
        mock_ui_bus,
    ) -> None:
        """Test that Supervisor properly stores all injected dependencies."""
        supervisor = Supervisor(
            agent_manager=mock_agent_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )

        assert supervisor.agent_manager is mock_agent_manager
        assert supervisor.session_manager is mock_session_manager
        assert supervisor.ui_bus is mock_ui_bus

    def test_initialization_with_required_dependencies(
        self,
        shallow_supervisor: Supervisor,
    ) -> None:
        """Test that Supervisor requires all necessary dependencies."""
        # All dependencies should be present
        assert hasattr(shallow_supervisor, "agent_manager")
        assert hasattr(shallow_supervisor, "session_manager")
        assert hasattr(shallow_supervisor, "ui_bus")

        # Dependencies should not be None
        assert shallow_supervisor.agent_manager is not None
        assert shallow_supervisor.session_manager is not None
        assert shallow_supervisor.ui_bus is not None

    def test_supervisor_has_run_async_method(
        self,
        shallow_supervisor: Supervisor,
    ) -> None:
        """Test that Supervisor implements the required run_async method."""
        assert hasattr(shallow_supervisor, "run_async")
        assert callable(shallow_supervisor.run_async)

    def test_supervisor_docstring_and_module_info(self) -> None:
        """Test that Supervisor has proper documentation."""
        assert Supervisor.__doc__ is not None
        assert len(Supervisor.__doc__.strip()) > 0
        assert (
            "workflow" in Supervisor.__doc__.lower()
            or "supervisor" in Supervisor.__doc__.lower()
        )

    def test_initialization_parameter_types(
        self,
        mock_agent_manager,
        mock_session_manager,
        mock_ui_bus,
    ) -> None:
        """Test that initialization accepts correct parameter types."""
        # Should accept valid mocks without error
        supervisor = Supervisor(
            agent_manager=mock_agent_manager,
            session_manager=mock_session_manager,
            ui_bus=mock_ui_bus,
        )
        assert isinstance(supervisor, Supervisor)

        # Verify the dependencies are stored with correct references
        assert id(supervisor.agent_manager) == id(mock_agent_manager)
        assert id(supervisor.session_manager) == id(mock_session_manager)
        assert id(supervisor.ui_bus) == id(mock_ui_bus)
