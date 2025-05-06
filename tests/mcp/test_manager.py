# tests/mcp/test_manager.py
import logging
import pathlib as real_pathlib  # Import the real pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call, mock_open

import pytest
import yaml
from pydantic import ValidationError

# Mock target needs actual type for isinstance checks
import streetrace.mcp.client

# Module under test
from streetrace.mcp.manager import (
    DEFAULT_CONFIG_PATH,
    MCPClientManager,
    MCPConfigError,
    MCPServerConfig,
)

# --- Fixtures ---


@pytest.fixture
def mock_mcp_client_class(mocker: pytest.MonkeyPatch) -> Mock:
    """Fixture to mock the MCPClient class constructor."""
    # Use autospec=True for better mock matching
    return mocker.patch("streetrace.mcp.manager.MCPClient", autospec=True)


@pytest.fixture
def mock_path(mocker: pytest.MonkeyPatch) -> tuple[Mock, MagicMock, Mock]:
    """Fixture to mock pathlib.Path operations."""
    # Create mock instances using the *real* pathlib.Path for spec
    mock_path_instance = MagicMock(spec=real_pathlib.Path)
    mock_home_path_instance = MagicMock(spec=real_pathlib.Path)

    # Configure mock_path_instance (returned by Path() calls)
    mock_path_instance.exists.return_value = True
    mock_open_obj = mock_open()
    mock_path_instance.open = mock_open_obj
    mock_path_instance.expanduser.return_value = mock_path_instance
    mock_path_instance.as_posix.return_value = "/mock/path/.streetrace/mcp_servers.yaml"

    # Configure mock_home_path_instance (returned by Path.home())
    # Make division return the main mock_path_instance after chaining
    division_mock = MagicMock()
    mock_home_path_instance.__truediv__.return_value = division_mock
    division_mock.__truediv__.return_value = mock_path_instance

    # Patch Path.home first
    mocker.patch(
        "streetrace.mcp.manager.pathlib.Path.home",
        return_value=mock_home_path_instance,
    )

    # Patch Path constructor last
    mock_path_class = mocker.patch(
        "streetrace.mcp.manager.pathlib.Path",
        return_value=mock_path_instance,
    )

    return mock_path_class, mock_path_instance, mock_open_obj


@pytest.fixture
def mock_yaml_load(mocker: pytest.MonkeyPatch) -> Mock:
    """Fixture to mock yaml.safe_load."""
    return mocker.patch("streetrace.mcp.manager.yaml.safe_load")


# --- Helper Function ---
def create_config_yaml(servers: list[dict[str, Any]]) -> str:
    """Create a YAML string from a list of server configs."""
    return yaml.dump({"servers": servers})


# --- Test Cases ---

# --- Initialization and Config Loading ---


@pytest.mark.usefixtures("mock_yaml_load")
def test_manager_init_default_path(mock_path: tuple[Mock, MagicMock, Mock]):
    """Test manager initializes with default config path ~/.streetrace/mcp_servers.yaml."""
    mock_path_class, mock_path_instance, _ = mock_path
    mock_path_instance.exists.return_value = False  # Simulate file not found

    # Get the expected default path string before creating the manager
    # This relies on the DEFAULT_CONFIG_PATH constant being accessible
    # Use the mocked Path constructor for consistency
    expected_default_path_arg = DEFAULT_CONFIG_PATH

    manager = MCPClientManager()

    # Verify Path class was called with the expected default path object
    mock_path_class.assert_called_with(expected_default_path_arg)
    mock_path_instance.expanduser.assert_called_once()
    mock_path_instance.exists.assert_called_once()
    # Check internal config list directly for verification
    assert not manager._config  # noqa: SLF001 Accessing private for test verification


@pytest.mark.usefixtures("mock_yaml_load")
def test_manager_init_custom_path(mock_path: tuple[Mock, MagicMock, Mock]):
    """Test manager initializes with a custom config path string."""
    mock_path_class, mock_path_instance, _ = mock_path
    mock_path_instance.exists.return_value = False
    custom_path_str = "/custom/path/mcp.yaml"

    manager = MCPClientManager(config_path=custom_path_str)

    mock_path_class.assert_called_with(custom_path_str)
    mock_path_instance.expanduser.assert_called_once()
    # Check internal state for verification
    config_path = manager._config_path  # noqa: SLF001 Accessing private for test
    assert config_path == mock_path_instance


@pytest.mark.usefixtures("mock_yaml_load")
def test_manager_load_config_file_not_found(
    mock_path: tuple[Mock, MagicMock, Mock],
    caplog: pytest.LogCaptureFixture,
):
    """Test config loading logs info and returns empty config if file not found."""
    mock_path_class, mock_path_instance, _ = mock_path
    mock_path_instance.exists.return_value = False

    manager = MCPClientManager()

    assert "Configuration file not found at" in caplog.text
    assert not manager.get_server_configs()


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_empty_yaml(
    mock_yaml_load: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test config loading handles empty or null YAML content gracefully."""
    mock_yaml_load.return_value = None

    manager = MCPClientManager()

    # Update expected log message
    assert "Config file at" in caplog.text
    assert "is empty or invalid format (missing 'servers' list)" in caplog.text
    assert not manager.get_server_configs()


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_missing_servers_key(
    mock_yaml_load: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test config loading handles YAML without the 'servers' key."""
    mock_yaml_load.return_value = {"other_key": "value"}

    manager = MCPClientManager()

    # Update expected log message
    assert "Config file at" in caplog.text
    assert "is empty or invalid format (missing 'servers' list)" in caplog.text
    assert not manager.get_server_configs()


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_servers_not_list(
    mock_yaml_load: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test config loading handles 'servers' key not being a list."""
    mock_yaml_load.return_value = {"servers": {"name": "a"}}

    manager = MCPClientManager()

    # Update expected log message
    assert "Config file at" in caplog.text
    assert "is empty or invalid format (missing 'servers' list)" in caplog.text
    assert not manager.get_server_configs()


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_yaml_error(mock_yaml_load: Mock):
    """Test MCPConfigError is raised on YAMLError during parsing."""
    mock_yaml_load.side_effect = yaml.YAMLError("Bad YAML")
    # Update expected error message pattern
    with pytest.raises(MCPConfigError, match=r"Error parsing YAML file .*: Bad YAML"):
        MCPClientManager()


def test_manager_load_config_read_error(mock_path: tuple[Mock, MagicMock, Mock]):
    """Test MCPConfigError is raised on OSError during file reading."""
    mock_path_class, mock_path_instance, mock_open_obj = mock_path
    mock_open_obj.side_effect = OSError("Permission denied")
    # Update expected error message pattern
    with pytest.raises(
        MCPConfigError,
        match=r"Error reading file .*: Permission denied",
    ):
        MCPClientManager()


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_valid_basic(mock_yaml_load: Mock):
    """Test loading a basic valid configuration creates MCPServerConfig objects."""
    valid_config = [
        {"name": "server1", "command": "cmd1", "args": ["a"]},
        {"name": "server2", "command": "cmd2", "args": [], "enabled": False},
    ]
    mock_yaml_load.return_value = {"servers": valid_config}

    manager = MCPClientManager()
    loaded_configs = manager.get_server_configs()

    assert len(loaded_configs) == 2
    assert isinstance(loaded_configs[0], MCPServerConfig)
    assert loaded_configs[0].name == "server1"
    assert loaded_configs[0].enabled is True
    assert isinstance(loaded_configs[1], MCPServerConfig)
    assert loaded_configs[1].name == "server2"
    assert loaded_configs[1].enabled is False


@pytest.mark.usefixtures("mock_path")
def test_manager_load_config_validation_skips_invalid(
    mock_yaml_load: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test Pydantic validation skips invalid entries and logs warnings."""
    invalid_configs = [
        {"name": "valid1", "command": "cmd1"},  # Valid
        {"name": "no_command"},  # Invalid: missing command
        {
            "name": "bad_args",
            "command": "cmd",
            "args": "not_a_list",
        },  # Invalid: bad args type
        {
            "name": "bad_env",
            "command": "cmd",
            "env": ["not_a_dict"],
        },  # Invalid: bad env type
        {"name": "valid2", "command": "cmd2", "transport": "stdio"},  # Valid
        {"name": "valid1", "command": "cmd3"},  # Invalid: Duplicate name
        "not_a_dict",  # Invalid: Not a dict
    ]
    mock_yaml_load.return_value = {"servers": invalid_configs}

    manager = MCPClientManager()
    loaded_configs = manager.get_server_configs()

    assert len(loaded_configs) == 2
    assert loaded_configs[0].name == "valid1"
    assert loaded_configs[1].name == "valid2"

    assert "Skipping invalid config index 1" in caplog.text
    assert "Skipping invalid config index 2" in caplog.text
    assert "Skipping invalid config index 3" in caplog.text
    # Fix: Update expected log message for duplicate name
    assert "Skipping config index 5: duplicate name 'valid1'" in caplog.text
    assert "Skipping invalid config index 6: Item is not a dictionary" in caplog.text


def test_pydantic_model_validation():
    """Test MCPServerConfig Pydantic model validation logic directly."""
    # Valid cases
    cfg1 = MCPServerConfig(name="n1", command="c1")
    assert cfg1.enabled is True
    assert cfg1.transport == "stdio"
    assert cfg1.args == []
    assert cfg1.env == {}

    cfg2 = MCPServerConfig(name="n2", command="c2", enabled="true", args=["a", "b"])
    assert cfg2.enabled is True
    assert cfg2.args == ["a", "b"]

    cfg3 = MCPServerConfig(name="n3", command="c3", enabled=False)
    assert cfg3.enabled is False

    # Invalid cases
    with pytest.raises(ValidationError):
        MCPServerConfig(name="i1", command="c1", args="bad")  # args not a list
    with pytest.raises(ValidationError):
        MCPServerConfig(name="i2", command="c2", transport="http")  # invalid transport
    with pytest.raises(ValidationError):
        MCPServerConfig(name="i3", command="c3", enabled="maybe")  # invalid bool
    with pytest.raises(ValidationError):
        MCPServerConfig(name="i4")  # missing command
    with pytest.raises(ValidationError):
        MCPServerConfig(command="c5")  # missing name


# --- Context Management Tests (__aenter__ / __aexit__) ---


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_aenter_no_enabled_servers(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
):
    """Test __aenter__ does nothing if no servers are enabled in config."""
    configs = [
        {"name": "s1", "command": "c1", "enabled": False},
        {"name": "s2", "command": "c2", "enabled": False},
    ]
    mock_yaml_load.return_value = {"servers": configs}

    manager = MCPClientManager()
    async with manager:
        assert not manager.get_active_clients()
        mock_mcp_client_class.assert_not_called()

    assert not manager.get_active_clients()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_aenter_success_starts_clients(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
):
    """Test successful __aenter__ creates and starts enabled clients."""
    raw_configs = [
        {"name": "server_a", "command": "cmd_a", "args": ["1"]},  # enabled by default
        {"name": "server_b", "command": "cmd_b", "enabled": True},
        {"name": "server_c", "command": "cmd_c", "enabled": False},
    ]
    mock_yaml_load.return_value = {"servers": raw_configs}

    # Pydantic models with defaults filled in (what MCPClient will receive)
    expected_config_a = MCPServerConfig(**raw_configs[0])
    expected_config_b = MCPServerConfig(**raw_configs[1])

    client_mocks: list[AsyncMock] = []

    # Side effect to create distinct mocks for each client
    def client_side_effect(config_dict: dict[str, Any]) -> AsyncMock:
        instance = AsyncMock(spec=streetrace.mcp.client.MCPClient)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.server_name = config_dict.get("name", "unknown_mock")
        client_mocks.append(instance)
        return instance

    mock_mcp_client_class.side_effect = client_side_effect
    manager = MCPClientManager()

    async with manager:
        # Assert MCPClient was instantiated for enabled servers with correct config
        assert mock_mcp_client_class.call_count == 2
        # Use model_dump() to get the dict passed to MCPClient constructor
        expected_calls = [
            call(expected_config_a.model_dump()),
            call(expected_config_b.model_dump()),
        ]
        mock_mcp_client_class.assert_has_calls(expected_calls, any_order=False)

        assert len(client_mocks) == 2
        assert len(manager.get_active_clients()) == 2
        assert "server_a" in manager.get_active_clients()
        assert "server_b" in manager.get_active_clients()
        assert "server_c" not in manager.get_active_clients()

        # Assert __aenter__ was called on each created client mock
        for client_mock in client_mocks:
            client_mock.__aenter__.assert_awaited_once()
            client_mock.__aexit__.assert_not_awaited()

    # Assert __aexit__ was called on each client mock after exiting context
    for client_mock in client_mocks:
        client_mock.__aexit__.assert_awaited_once()

    assert not manager.get_active_clients()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_aenter_partial_failure_logs_and_continues(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test __aenter__ logs errors but continues if some clients fail to start."""
    configs = [
        {"name": "ok_server", "command": "cmd_ok"},
        {"name": "fail_server", "command": "cmd_fail"},
        {"name": "ok_server2", "command": "cmd_ok2"},
    ]
    mock_yaml_load.return_value = {"servers": configs}
    client_mocks: list[AsyncMock] = []
    fail_connection_error = streetrace.mcp.client.MCPClientConnectionError(
        "Connection failed",
    )

    # Side effect to simulate one client failing to start
    def client_side_effect(config: dict[str, Any]) -> AsyncMock:
        instance = AsyncMock(spec=streetrace.mcp.client.MCPClient)
        instance.server_name = config.get("name", "unknown_mock")
        if instance.server_name == "fail_server":
            instance.__aenter__ = AsyncMock(side_effect=fail_connection_error)
        else:
            instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        client_mocks.append(instance)
        return instance

    mock_mcp_client_class.side_effect = client_side_effect
    manager = MCPClientManager()

    async with manager:
        assert mock_mcp_client_class.call_count == 3
        assert len(client_mocks) == 3
        assert len(manager.get_active_clients()) == 2
        assert "ok_server" in manager.get_active_clients()
        assert "ok_server2" in manager.get_active_clients()
        assert "fail_server" not in manager.get_active_clients()

        # Check log message for the failed client
        assert "Failed to initialize client for server 'fail_server'" in caplog.text
        assert "Connection failed" in caplog.text  # Underlying error message

        # Check __aenter__ was awaited on all mocks
        for client_mock in client_mocks:
            client_mock.__aenter__.assert_awaited_once()

    # Verify cleanup: __aexit__ called only for successfully started clients
    successful_clients = [cm for cm in client_mocks if cm.server_name != "fail_server"]
    failed_client = next(cm for cm in client_mocks if cm.server_name == "fail_server")

    for client_mock in successful_clients:
        client_mock.__aexit__.assert_awaited_once()
    failed_client.__aexit__.assert_not_awaited()  # Should not be called if __aenter__ failed

    assert not manager.get_active_clients()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_aexit_partial_failure_logs_and_continues(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """Test __aexit__ logs errors but continues if some clients fail to stop."""
    caplog.set_level(logging.INFO)  # Ensure INFO messages are captured
    configs = [
        {"name": "ok_exit", "command": "cmd_ok"},
        {"name": "fail_exit", "command": "cmd_fail"},
    ]
    mock_yaml_load.return_value = {"servers": configs}
    client_mocks: list[AsyncMock] = []
    fail_exit_error = RuntimeError("Shutdown failed")

    # Side effect to simulate one client failing to stop
    def client_side_effect(config: dict[str, Any]) -> AsyncMock:
        instance = AsyncMock(spec=streetrace.mcp.client.MCPClient)
        instance.server_name = config.get("name", "unknown_mock")
        instance.__aenter__ = AsyncMock(return_value=instance)
        if instance.server_name == "fail_exit":
            instance.__aexit__ = AsyncMock(side_effect=fail_exit_error)
        else:
            instance.__aexit__ = AsyncMock(return_value=None)
        client_mocks.append(instance)
        return instance

    mock_mcp_client_class.side_effect = client_side_effect
    manager = MCPClientManager()

    # Enter and exit the context manager
    async with manager:
        assert len(manager.get_active_clients()) == 2

    # Verify state after exit
    assert not manager.get_active_clients()
    assert len(client_mocks) == 2

    # Verify __aexit__ was called on all mocks
    for client_mock in client_mocks:
        client_mock.__aexit__.assert_awaited_once()

    # Check logs for both success and failure messages
    assert "Error during shutdown of client 'fail_exit'" in caplog.text
    assert "Shutdown failed" in caplog.text  # Underlying error
    assert "Client 'ok_exit' shutdown completed." in caplog.text


# --- Accessor Methods ---


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_get_client(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
):
    """Test get_client returns the correct active client or None."""
    configs = [{"name": "server1", "command": "cmd1"}]
    mock_yaml_load.return_value = {"servers": configs}
    client_mocks: list[AsyncMock] = []

    # Side effect to store created mocks
    def client_side_effect(config: dict[str, Any]) -> AsyncMock:
        instance = AsyncMock(spec=streetrace.mcp.client.MCPClient)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.server_name = config["name"]
        client_mocks.append(instance)
        return instance

    mock_mcp_client_class.side_effect = client_side_effect
    manager = MCPClientManager()

    # Before context: client should not exist
    assert manager.get_client("server1") is None
    assert manager.get_client("nonexistent") is None

    async with manager:
        assert len(client_mocks) == 1
        assert manager.get_client("server1") is client_mocks[0]
        assert manager.get_client("nonexistent") is None

    # After context: client should be gone
    assert manager.get_client("server1") is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_path")
async def test_manager_get_active_clients_and_list_names(
    mock_yaml_load: Mock,
    mock_mcp_client_class: Mock,
):
    """Test get_active_clients returns a copy and list_active_client_names works."""
    configs = [
        {"name": "client_x", "command": "cx"},
        {"name": "client_y", "command": "cy"},
    ]
    mock_yaml_load.return_value = {"servers": configs}
    client_mocks_map: dict[str, AsyncMock] = {}

    # Side effect to store created mocks by name
    def client_side_effect(config: dict[str, Any]) -> AsyncMock:
        instance = AsyncMock(spec=streetrace.mcp.client.MCPClient)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.server_name = config["name"]
        client_mocks_map[instance.server_name] = instance
        return instance

    mock_mcp_client_class.side_effect = client_side_effect
    manager = MCPClientManager()

    # Before context
    assert manager.get_active_clients() == {}
    assert manager.list_active_client_names() == []

    async with manager:
        active_clients = manager.get_active_clients()
        assert len(active_clients) == 2
        assert "client_x" in active_clients
        assert "client_y" in active_clients
        assert active_clients["client_x"] is client_mocks_map["client_x"]
        assert active_clients["client_y"] is client_mocks_map["client_y"]

        # Test that the returned dict is a copy
        active_clients["new"] = "mutate"
        assert "new" not in manager.get_active_clients()

        # Test list names
        active_names = manager.list_active_client_names()
        assert sorted(active_names) == ["client_x", "client_y"]

    # After context
    assert manager.get_active_clients() == {}
    assert manager.list_active_client_names() == []


# --- Test get_server_configs ---


@pytest.mark.usefixtures("mock_path")
def test_get_server_configs(mock_yaml_load: Mock):
    """Test get_server_configs returns the parsed and validated configs."""
    valid_config = [
        {"name": "server1", "command": "cmd1"},
        {"name": "server2", "command": "cmd2", "enabled": False},
    ]
    mock_yaml_load.return_value = {"servers": valid_config}

    manager = MCPClientManager()
    configs = manager.get_server_configs()

    assert len(configs) == 2
    assert configs[0].name == "server1"
    assert configs[1].name == "server2"

    # Verify it returns a copy (or is immutable)
    configs.append(MCPServerConfig(name="mutated", command="mut"))
    assert len(manager.get_server_configs()) == 2
