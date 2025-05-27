"""Tests for the ModelFactory class."""

from unittest.mock import MagicMock, patch

import pytest

from streetrace.llm.model_factory import ModelFactory


@pytest.fixture
def mock_ui_bus():
    """Create a mock UiBus."""
    return MagicMock()


@pytest.fixture
def model_config():
    """Create a sample model configuration."""
    return {
        "default_model": "gpt-3.5-turbo",
        "gpt4": "gpt-4",
        "gemini": "gemini/gemini-pro",
    }


@pytest.fixture
def model_factory(model_config, mock_ui_bus):
    """Create a ModelFactory instance with the test configuration."""
    return ModelFactory(model_config, mock_ui_bus)


@patch("streetrace.llm.model_factory.get_llm_interface")
def test_get_default_model(mock_get_llm_interface, model_factory, mock_ui_bus):
    """Test retrieving the default model."""
    # Arrange
    mock_llm_interface = MagicMock()
    mock_llm_interface.get_adk_llm.return_value = "default_model_instance"
    mock_get_llm_interface.return_value = mock_llm_interface

    # Act
    result = model_factory.get_current_model()

    # Assert
    assert result == "default_model_instance"
    mock_get_llm_interface.assert_called_once_with("gpt-3.5-turbo", mock_ui_bus)
    mock_llm_interface.get_adk_llm.assert_called_once()


@patch("streetrace.llm.model_factory.get_llm_interface")
def test_get_model_by_name(mock_get_llm_interface, model_factory, mock_ui_bus):
    """Test retrieving a model by name."""
    # Arrange
    mock_llm_interface = MagicMock()
    mock_llm_interface.get_adk_llm.return_value = "gemini_model_instance"
    mock_get_llm_interface.return_value = mock_llm_interface

    # Act
    result = model_factory.get_model("gemini")

    # Assert
    assert result == "gemini_model_instance"
    mock_get_llm_interface.assert_called_once_with("gemini/gemini-pro", mock_ui_bus)
    mock_llm_interface.get_adk_llm.assert_called_once()


@patch("streetrace.llm.model_factory.get_llm_interface")
def test_get_model_default_alias(mock_get_llm_interface, model_factory, mock_ui_bus):
    """Test retrieving a model using the 'default' alias."""
    # Arrange
    mock_llm_interface = MagicMock()
    mock_llm_interface.get_adk_llm.return_value = "default_model_instance"
    mock_get_llm_interface.return_value = mock_llm_interface

    # Act
    result = model_factory.get_model("default")

    # Assert
    assert result == "default_model_instance"
    mock_get_llm_interface.assert_called_once_with("gpt-3.5-turbo", mock_ui_bus)
    mock_llm_interface.get_adk_llm.assert_called_once()


def test_get_model_invalid_name(model_factory):
    """Test retrieving a model with an invalid name."""
    # Act & Assert
    with pytest.raises(
        ValueError, match="Model 'invalid_model' not found in configuration"
    ):
        model_factory.get_model("invalid_model")


@patch("streetrace.llm.model_factory.get_llm_interface")
def test_get_llm_interface(mock_get_llm_interface, model_factory, mock_ui_bus):
    """Test retrieving the LlmInterface for a model."""
    # Arrange
    mock_llm_interface = MagicMock()
    mock_get_llm_interface.return_value = mock_llm_interface

    # Act
    result = model_factory.get_llm_interface("gpt4")

    # Assert
    assert result == mock_llm_interface
    mock_get_llm_interface.assert_called_once_with("gpt-4", mock_ui_bus)


@patch("streetrace.llm.model_factory.get_llm_interface")
def test_caching_behavior(mock_get_llm_interface, model_factory, mock_ui_bus):
    """Test that model interfaces are properly cached."""
    # Arrange
    mock_llm_interface1 = MagicMock()
    mock_llm_interface2 = MagicMock()
    mock_get_llm_interface.side_effect = [mock_llm_interface1, mock_llm_interface2]

    # Act
    interface1 = model_factory.get_llm_interface("gpt4")
    interface2 = model_factory.get_llm_interface("gpt4")  # Should be cached
    interface3 = model_factory.get_llm_interface("gemini")  # Should create new

    # Assert
    assert interface1 == interface2  # Same instance from cache
    assert interface1 != interface3  # Different instance
    assert mock_get_llm_interface.call_count == 2  # Only called for unique models
