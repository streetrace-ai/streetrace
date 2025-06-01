"""Unit tests for the agent_loader module."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from streetrace.agents.agent_loader import (
    AgentInfo,
    _get_streetrace_agent_class,
    _import_agent_module,
    _validate_impl,
    get_agent_impl,
    get_available_agents,
)
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

# ===== Fixtures =====


@pytest.fixture
def mock_agent_dir():
    """Create a mock agent directory path."""
    return Path("/fake/agent/directory")


@pytest.fixture
def mock_agent_module():
    """Create a mock agent module."""
    mock_module = Mock(spec=ModuleType)
    mock_module.__name__ = "mock_agent_module"
    return mock_module


@pytest.fixture
def mock_agent_card():
    """Create a mock StreetRaceAgentCard."""
    mock_card = MagicMock(spec=StreetRaceAgentCard)
    mock_card.name = "MockAgent"
    mock_card.description = "A mock agent for testing"
    mock_card.version = "1.0.0"
    return mock_card


@pytest.fixture
def mock_agent_instance(mock_agent_card):
    """Create a mock agent instance."""
    mock_instance = MagicMock()
    mock_instance.get_agent_card.return_value = mock_agent_card
    return mock_instance


# ===== Test _import_agent_module function =====


def test_import_agent_module_file_not_found(mock_agent_dir):
    """Test importing an agent module when the file is not found."""
    with (
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(FileNotFoundError),
    ):
        _import_agent_module(mock_agent_dir)


def test_import_agent_module_not_file(mock_agent_dir):
    """Test importing an agent module when the path is not a file."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=False),
        pytest.raises(FileNotFoundError),
    ):
        _import_agent_module(mock_agent_dir)


def test_import_agent_module_spec_creation_failure(mock_agent_dir):
    """Test importing an agent module when spec creation fails."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
        patch("importlib.util.spec_from_file_location", return_value=None),
    ):
        assert _import_agent_module(mock_agent_dir) is None


def test_import_agent_module_import_error(mock_agent_dir):
    """Test importing an agent module when import fails."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        mock_spec = MagicMock()
        mock_loader = MagicMock()
        mock_spec.loader = mock_loader

        with (
            patch("importlib.util.spec_from_file_location", return_value=mock_spec),
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
        ):
            mock_module_from_spec.side_effect = ImportError("Import failed")

            with pytest.raises(ValueError) as excinfo:
                _import_agent_module(mock_agent_dir)

            assert "Import failed" in str(excinfo.value)


def test_import_agent_module_success(mock_agent_dir):
    """Test successfully importing an agent module."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        mock_spec = MagicMock()
        mock_loader = MagicMock()
        mock_spec.loader = mock_loader
        mock_module = MagicMock()

        with (
            patch("importlib.util.spec_from_file_location", return_value=mock_spec),
            patch("importlib.util.module_from_spec", return_value=mock_module),
        ):
            result = _import_agent_module(mock_agent_dir)

            assert result == mock_module
            mock_loader.exec_module.assert_called_once_with(mock_module)
            # Verify module was added to sys.modules
            module_name = f"agent_module_{mock_agent_dir.name}"
            assert sys.modules.get(module_name) == mock_module


# ===== Test _get_streetrace_agent_class function =====


def test_get_streetrace_agent_class_empty_module(mock_agent_module):
    """Test getting a StreetRaceAgent class from an empty module."""
    # Mock the dir() function when called on the module
    with patch("streetrace.agents.agent_loader.dir", return_value=[]):
        result = _get_streetrace_agent_class(mock_agent_module)
        assert result is None


def test_get_streetrace_agent_class_no_matching_class(mock_agent_module):
    """Test getting a StreetRaceAgent class when no matching class exists."""

    # Mock getattr to return non-class attributes
    def mock_getattr(_obj, name):
        if name == "some_value":
            return "not a class"
        if name == "OtherClass":
            # Return a class with a different module
            class OtherClass:
                pass

            OtherClass.__module__ = "other_module"
            return OtherClass
        return None

    # Mock the dir and getattr functions
    with (
        patch(
            "streetrace.agents.agent_loader.dir",
            return_value=["some_value", "OtherClass"],
        ),
        patch("streetrace.agents.agent_loader.getattr", mock_getattr),
        patch(
            "streetrace.agents.agent_loader.isinstance",
            side_effect=lambda obj, _cls: isinstance(obj, type),
        ),
    ):
        result = _get_streetrace_agent_class(mock_agent_module)
        assert result is None


def test_get_streetrace_agent_class_found_class(create_agent_module):
    """Test finding a StreetRaceAgent class in a module."""
    # Create a module with a StreetRaceAgent subclass
    module = create_agent_module()

    # Get the actual implementation
    result = _get_streetrace_agent_class(module)

    # Verify it found the class
    assert result is not None
    assert result.__name__ == "TestAgent"
    assert issubclass(result, StreetRaceAgent)


# ===== Test _validate_impl function =====


@patch("streetrace.agents.agent_loader._import_agent_module")
def test_validate_impl_import_failure(mock_import_module, mock_agent_dir):
    """Test validating an agent implementation when import fails."""
    mock_import_module.return_value = None

    with pytest.raises(ValueError) as excinfo:
        _validate_impl(mock_agent_dir)

    assert "Failed to import agent module" in str(excinfo.value)


@patch("streetrace.agents.agent_loader._import_agent_module")
@patch("streetrace.agents.agent_loader._get_streetrace_agent_class")
def test_validate_impl_no_agent_class(
    mock_get_agent_class,
    mock_import_module,
    mock_agent_dir,
    mock_agent_module,
):
    """Test validating an agent implementation when no agent class is found."""
    mock_import_module.return_value = mock_agent_module
    mock_get_agent_class.return_value = None

    with pytest.raises(ValueError) as excinfo:
        _validate_impl(mock_agent_dir)

    assert "No StreetRaceAgent implementation found" in str(excinfo.value)


@patch("streetrace.agents.agent_loader._import_agent_module")
@patch("streetrace.agents.agent_loader._get_streetrace_agent_class")
def test_validate_impl_agent_card_error(
    mock_get_agent_class,
    mock_import_module,
    mock_agent_dir,
    mock_agent_module,
):
    """Test validating an agent implementation when getting the agent card fails."""
    mock_import_module.return_value = mock_agent_module

    # Create a mock agent class that raises an exception
    mock_agent_class = MagicMock(spec=type)
    mock_agent_instance = MagicMock()
    mock_agent_instance.get_agent_card.side_effect = Exception(
        "Failed to get agent card",
    )
    mock_agent_class.return_value = mock_agent_instance

    mock_get_agent_class.return_value = mock_agent_class

    with pytest.raises(ValueError) as excinfo:
        _validate_impl(mock_agent_dir)

    assert "Failed to get agent card" in str(excinfo.value)


@patch("streetrace.agents.agent_loader._import_agent_module")
@patch("streetrace.agents.agent_loader._get_streetrace_agent_class")
def test_validate_impl_success(
    mock_get_agent_class,
    mock_import_module,
    mock_agent_dir,
    mock_agent_module,
    mock_agent_card,
):
    """Test successfully validating an agent implementation."""
    mock_import_module.return_value = mock_agent_module

    # Create a mock agent class
    mock_agent_class = MagicMock(spec=type)
    mock_agent_instance = MagicMock()
    mock_agent_instance.get_agent_card.return_value = mock_agent_card
    mock_agent_class.return_value = mock_agent_instance

    mock_get_agent_class.return_value = mock_agent_class

    result = _validate_impl(mock_agent_dir)

    assert isinstance(result, AgentInfo)
    assert result.agent_card == mock_agent_card
    assert result.module == mock_agent_module


# ===== Test get_available_agents function =====


def test_get_available_agents_no_dirs():
    """Test getting available agents when no directories exist."""
    with patch("pathlib.Path.exists", return_value=False):
        result = get_available_agents([Path("/fake/path")])
        assert result == []


@patch("streetrace.agents.agent_loader._validate_impl")
def test_get_available_agents_validation_error(mock_validate_impl):
    """Test getting available agents when validation fails for some agents."""
    mock_base_dir = Path("/fake/base/dir")
    mock_agent_dir1 = mock_base_dir / "agent1"
    mock_agent_dir2 = mock_base_dir / "agent2"

    # Mock base directory exists and is a directory
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        # Mock iterdir to return two agent directories
        patch(
            "pathlib.Path.iterdir",
            return_value=[mock_agent_dir1, mock_agent_dir2],
        ),
    ):
        # First agent fails validation, second succeeds
        mock_validate_impl.side_effect = [
            ValueError("Invalid agent"),
            MagicMock(spec=AgentInfo),
        ]

        result = get_available_agents([mock_base_dir])

        # Should only include the successful agent
        assert len(result) == 1
        assert isinstance(result[0], AgentInfo)


@patch("streetrace.agents.agent_loader._validate_impl")
def test_get_available_agents_success(
    mock_validate_impl,
    mock_agent_card,
    mock_agent_module,
):
    """Test successfully getting available agents."""
    mock_base_dir = Path("/fake/base/dir")
    mock_agent_dir1 = mock_base_dir / "agent1"
    mock_agent_dir2 = mock_base_dir / "agent2"

    # Create mock agent info objects
    mock_agent_info1 = AgentInfo(
        agent_card=mock_agent_card,
        module=mock_agent_module,
    )
    mock_agent_info2 = AgentInfo(
        agent_card=mock_agent_card,
        module=mock_agent_module,
    )

    # Mock base directory exists and is a directory
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch(
            "pathlib.Path.iterdir",
            return_value=[mock_agent_dir1, mock_agent_dir2],
        ),
    ):
        # Mock iterdir to return two agent directories
        # Both agents validate successfully
        mock_validate_impl.side_effect = [mock_agent_info1, mock_agent_info2]

        result = get_available_agents([mock_base_dir])

        assert len(result) == 2
        assert result[0] == mock_agent_info1
        assert result[1] == mock_agent_info2


# ===== Test get_agent_impl function =====


@patch("streetrace.agents.agent_loader._get_streetrace_agent_class")
def test_get_agent_impl_no_class(
    mock_get_agent_class,
    mock_agent_module,
    mock_agent_card,
):
    """Test getting an agent implementation when no class is found."""
    mock_get_agent_class.return_value = None

    agent_info = AgentInfo(
        agent_card=mock_agent_card,
        module=mock_agent_module,
    )

    with pytest.raises(ValueError) as excinfo:
        get_agent_impl(agent_info)

    assert "No StreetRaceAgent implementation found" in str(excinfo.value)


@patch("streetrace.agents.agent_loader._get_streetrace_agent_class")
def test_get_agent_impl_success(
    mock_get_agent_class,
    mock_agent_module,
    mock_agent_card,
):
    """Test successfully getting an agent implementation."""
    mock_agent_class = MagicMock(spec=type)
    mock_get_agent_class.return_value = mock_agent_class

    agent_info = AgentInfo(
        agent_card=mock_agent_card,
        module=mock_agent_module,
    )

    result = get_agent_impl(agent_info)

    assert result == mock_agent_class
