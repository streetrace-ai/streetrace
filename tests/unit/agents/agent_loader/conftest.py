"""Pytest fixtures for agent_loader tests."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


@pytest.fixture(autouse=True)
def cleanup_sys_modules():
    """Clean up any dynamically created modules after each test."""
    # Store the original modules
    original_modules = set(sys.modules.keys())

    # Run the test
    yield

    # Clean up any new modules starting with "agent_module_"
    for module_name in list(sys.modules.keys()):
        if (
            module_name.startswith("agent_module_")
            and module_name not in original_modules
        ):
            del sys.modules[module_name]


@pytest.fixture
def mock_street_race_agent_base():
    """Create a mock StreetRaceAgent base class for testing inheritance detection."""
    # Create a fake version of StreetRaceAgent for testing _get_streetrace_agent_class
    # Avoid circular imports due to string checks in real detection
    mock_base = MagicMock(spec=type)
    mock_base.__name__ = "StreetRaceAgent"
    mock_base.__module__ = "streetrace.agents.street_race_agent"
    return mock_base


@pytest.fixture
def create_agent_module():
    """Fixture to create a mock agent module with custom classes."""

    def _create_module(name="test_agent_module", include_agent=True):
        """Create a module with optional agent class.

        Args:
            name: Name for the module
            include_agent: Whether to include a StreetRaceAgent subclass

        Returns:
            The created module

        """
        # Create a new module
        module = ModuleType(name)

        # Add module to sys.modules to simulate proper import
        sys.modules[name] = module

        if include_agent:
            # Define a StreetRaceAgent subclass
            class TestAgent(StreetRaceAgent):
                """Test agent implementation."""

                def get_agent_card(self):
                    """Provide the agent card."""
                    return StreetRaceAgentCard(
                        capabilities=MagicMock(),
                        defaultInputModes=["text/plain"],
                        defaultOutputModes=["text/plain"],
                        description="Test agent",
                        name="TestAgent",
                        skills=[MagicMock()],
                        version="1.0.0",
                    )

                async def create_agent(self, model_factory, tools, system_context):  # noqa: ARG002
                    """Create the agent."""
                    return MagicMock()

            # Set the module name to simulate proper import behavior
            TestAgent.__module__ = name

            # Add the class to the module
            module.TestAgent = TestAgent  # type: ignore[attr-defined]

        return module

    return _create_module
