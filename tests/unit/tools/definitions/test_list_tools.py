"""Unit tests for the list_tools tool."""

from pathlib import Path
from unittest import mock

import pytest
import yaml

from streetrace.tools.definitions.list_tools import (
    _get_tools_from_config,
    _load_tools_config,
    list_tools,
)
from streetrace.tools.definitions.result import OpResultCode


@pytest.fixture
def mock_tools_config():
    """Create a mock tools configuration."""
    return {
        "tools": [
            {
                "name": "test_tool",
                "description": "A test tool",
                "source": "local",
                "module": "test.module",
                "function": "test_function",
                "requires_agent": False,
            },
            {
                "name": "agent_tool",
                "description": "A tool requiring agent",
                "source": "local",
                "module": "agent.module",
                "function": "agent_function",
                "requires_agent": True,
            },
        ],
    }


@pytest.fixture
def mock_config_file(tmp_path, mock_tools_config):
    """Create a mock configuration file."""
    config_dir = tmp_path / "tools"
    config_dir.mkdir()
    config_path = config_dir / "tools.yaml"

    with config_path.open("w") as f:
        yaml.dump(mock_tools_config, f)

    return config_path


def test_load_tools_config(mock_config_file):
    """Test loading tools configuration."""

    def mocked_exists(self):
        return self == mock_config_file

    # Test successful load
    with mock.patch("pathlib.Path.exists", new=mocked_exists):
        config = _load_tools_config(mock_config_file)
    assert config is not None
    assert "tools" in config
    assert len(config["tools"]) == 2

    # Test with non-existent file
    with pytest.raises(FileNotFoundError, match="Tools configuration file not found"):
        assert _load_tools_config(Path("/nonexistent/tools.yaml")) is None

    # Test with invalid YAML
    with (
        mock.patch("pathlib.Path.exists", return_value=True),
        mock.patch("pathlib.Path.is_file", return_value=True),
        mock.patch(
            "pathlib.Path.open",
            mock.mock_open(read_data="invalid: yaml: content:"),
        ),
        mock.patch(
            "yaml.safe_load",
            side_effect=yaml.YAMLError("Test error"),
        ),
        pytest.raises(
            yaml.YAMLError,
            match="Test error",
        ),
    ):
        assert _load_tools_config(Path("/fake/tools.yaml")) is None


def test_get_tools_from_config(mock_tools_config):
    """Test extracting tools from configuration."""
    # Test with valid config
    tools_dict = _get_tools_from_config(mock_tools_config)
    assert len(tools_dict) == 2
    tools = list(tools_dict.values())
    assert tools[0]["name"] == "test_tool"
    assert tools[1]["name"] == "agent_tool"

    # Test with invalid config formats
    assert _get_tools_from_config({}) == {}
    with pytest.raises(TypeError, match="expected list, got"):
        _get_tools_from_config({"tools": "not a list"})
    with pytest.raises(ValueError, match="No valid tools"):
        _get_tools_from_config({"tools": [{"no_name": "value"}]})

    # Test with mixed valid/invalid entries
    mixed_config = {"tools": [{"name": "valid"}, "invalid", {"no_name": "invalid"}]}
    tools = _get_tools_from_config(mixed_config)
    assert len(tools) == 1
    assert "valid" in tools
    assert tools["valid"]["name"] == "valid"


def test_list_tools(mock_config_file):
    """Test the list_tools function."""
    # Test with valid config file
    work_dir = mock_config_file.parent.parent

    def mocked_exists(self):
        return self == mock_config_file

    # Test successful load
    with mock.patch("pathlib.Path.exists", new=mocked_exists):
        result = list_tools(work_dir)
    assert result["result"] == OpResultCode.SUCCESS
    assert len(result["output"]) == 2
    assert result["output"][0]["name"] == "test_tool"

    # Test fallback to default tools
    with (
        mock.patch(
            "streetrace.tools.definitions.list_tools._load_tools_config",
            return_value={},
        ),
    ):
        result = list_tools(Path("/fake/work_dir"))
        assert result["result"] == OpResultCode.SUCCESS
        assert len(result["output"]) > 0  # Should have default tools

    # Test failure case
    with mock.patch(
        "streetrace.tools.definitions.list_tools._load_tools_config",
        side_effect=OSError("Test error"),
    ):
        result = list_tools(Path("/fake/work_dir"))
        assert result["result"] == OpResultCode.SUCCESS
        assert len(result["output"]) > 0  # Should have default tools
