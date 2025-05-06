# tests/mcp/test_client.py
import re  # Import re for regex matching
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from litellm.types.utils import ChatCompletionMessageToolCall
from mcp import ClientSession, McpError, StdioServerParameters
from mcp.types import (
    CallToolResult,
    ListResourcesResult,
    # ListToolsResult, # No longer used directly
    Resource,
    TextContent,
    # Tool, # No longer used directly
)

# Import new types for testing
from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from streetrace.mcp.client import (
    MCPClient,
    MCPClientConnectionError,
    MCPClientError,
    MCPClientInteractionError,
)
from streetrace.mcp.manager import MCPServerConfig

# --- Constants ---

VALID_SERVER_CONFIG_DICT = {
    "name": "test_server",
    "command": "echo",
    "args": ["hello"],
    "env": {"TEST_VAR": "value"},
    "enabled": True,
}
VALID_SERVER_CONFIG = MCPServerConfig(**VALID_SERVER_CONFIG_DICT)


INVALID_SERVER_CONFIG_DICT = {
    "name": "bad_server",
    # Missing command
    "args": [],
}

# A valid dummy URI for testing Resource
DUMMY_URI = "dummy://server/resource1"

# Create a mock error object for McpError tests
MOCK_MCP_ERROR_OBJ = SimpleNamespace(message="Proto error", code=-32000)

# --- Fixtures ---


@pytest.fixture
def mock_stdio_client(mocker):
    """Mock mcp.client.stdio.stdio_client."""
    mock_ctx_manager = AsyncMock()
    mock_ctx_manager.__aenter__.return_value = (
        AsyncMock(),  # read_stream
        AsyncMock(),  # write_stream
    )
    mock_ctx_manager.__aexit__.return_value = None
    return mocker.patch(
        "streetrace.mcp.client.stdio_client",
        return_value=mock_ctx_manager,
    )


@pytest.fixture
def mock_client_session(mocker):
    """Mock mcp.ClientSession class and instance."""
    mock_session_instance = AsyncMock(spec=ClientSession)
    mock_session_instance.initialize = AsyncMock(return_value=None)
    mock_session_instance.close = AsyncMock(return_value=None)
    mock_session_instance.list_resources = AsyncMock()
    mock_session_instance.read_resource = AsyncMock()
    mock_session_instance.list_prompts = AsyncMock()

    mock_session_instance.__aenter__.return_value = mock_session_instance
    mock_session_instance.__aexit__.return_value = None

    mock_session_class = mocker.patch(
        "streetrace.mcp.client.ClientSession",
        return_value=mock_session_instance,
    )

    return mock_session_class, mock_session_instance


@pytest.fixture
def mock_litellm_mcp_tools(mocker):
    """Mock litellm.experimental_mcp_client.tools module."""
    mock_module = MagicMock()
    mock_module.load_mcp_tools = AsyncMock()
    mock_module.call_openai_tool = AsyncMock()
    return mocker.patch("streetrace.mcp.client.litellm_mcp_tools", new=mock_module)


# --- Test Cases: Initialization ---


def get_client_config(client: MCPClient) -> dict[str, Any]:
    return client._config  # noqa: SLF001


def get_client_session(
    client: MCPClient,
) -> ClientSession | None:  # Return type can be None
    return client._session  # noqa: SLF001


def test_mcp_client_init_valid():
    """Test MCPClient initialization with valid config."""
    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    assert client.server_name == "test_server"
    assert get_client_config(client) == VALID_SERVER_CONFIG_DICT
    assert get_client_session(client) is None
    assert not client.is_active


def test_mcp_client_init_invalid():
    """Test MCPClient initialization with invalid config."""
    with pytest.raises(ValueError, match="must include 'name', 'command', and 'args'"):
        MCPClient(INVALID_SERVER_CONFIG_DICT)


# --- Test Cases: Context Management (__aenter__ / __aexit__) ---


@pytest.mark.asyncio
async def test_mcp_client_aenter_success(mock_stdio_client, mock_client_session):
    """Test successful __aenter__ establishes connection and session."""
    mock_session_class, mock_session_instance = mock_client_session
    client = MCPClient(VALID_SERVER_CONFIG_DICT)

    async with client:
        mock_stdio_client.assert_called_once()
        call_args, call_kwargs = mock_stdio_client.call_args
        params: StdioServerParameters = call_args[0]
        assert params.command == VALID_SERVER_CONFIG_DICT["command"]
        assert params.args == VALID_SERVER_CONFIG_DICT["args"]
        assert params.env == VALID_SERVER_CONFIG_DICT["env"]

        mock_session_class.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        assert client.is_active
        assert get_client_session(client) is mock_session_instance


@pytest.mark.asyncio
async def test_mcp_client_aenter_stdio_client_returns_invalid(mock_stdio_client):
    """Test __aenter__ fails if stdio_client returns invalid streams."""
    mock_stdio_client.return_value.__aenter__.return_value = (
        None  # Simulate invalid return
    )

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    expected_error_msg = (
        "stdio_client returned invalid transport streams for test_server"
    )
    with pytest.raises(MCPClientConnectionError, match=re.escape(expected_error_msg)):
        async with client:
            pass

    mock_stdio_client.assert_called_once()
    mock_stdio_client.return_value.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_client_aenter_command_not_found(mock_stdio_client):
    """Test __aenter__ raises MCPClientConnectionError if command is not found."""
    mock_stdio_client.side_effect = FileNotFoundError("command not found")
    client = MCPClient(VALID_SERVER_CONFIG_DICT)

    expected_error_msg = "Command not found for server 'test_server': echo"
    with pytest.raises(MCPClientConnectionError, match=re.escape(expected_error_msg)):
        async with client:
            pass

    mock_stdio_client.return_value.__aexit__.assert_not_awaited()


@pytest.mark.asyncio
async def test_mcp_client_aenter_session_init_mcp_error(
    mock_stdio_client,
    mock_client_session,
):
    """Test __aenter__ raises MCPClientConnectionError on McpError during session init."""
    mock_session_class, mock_session_instance = mock_client_session
    mock_session_instance.initialize.side_effect = McpError(
        MOCK_MCP_ERROR_OBJ,
    )
    client = MCPClient(VALID_SERVER_CONFIG_DICT)

    expected_error_msg = (
        "MCP protocol error connecting client 'test_server': Proto error"
    )
    with pytest.raises(MCPClientConnectionError, match=re.escape(expected_error_msg)):
        async with client:
            pass

    mock_stdio_client.assert_called_once()
    mock_session_class.assert_called_once()
    mock_session_instance.initialize.assert_awaited_once()
    mock_stdio_client.return_value.__aexit__.assert_awaited_once()
    mock_session_instance.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_client_aenter_generic_error_on_session_creation(
    mock_stdio_client,
    mock_client_session,
):
    """Test __aenter__ handles generic errors during ClientSession instantiation."""
    mock_session_class, mock_session_instance = mock_client_session
    generic_error_msg = "Generic setup error"
    mock_session_class.side_effect = RuntimeError(
        generic_error_msg,
    )
    client = MCPClient(VALID_SERVER_CONFIG_DICT)

    expected_error_msg = f"Failed to connect client 'test_server': {generic_error_msg}"
    with pytest.raises(MCPClientConnectionError, match=re.escape(expected_error_msg)):
        async with client:
            pass

    mock_stdio_client.assert_called_once()
    mock_session_class.assert_called_once()
    mock_session_instance.initialize.assert_not_awaited()
    mock_stdio_client.return_value.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_client_aexit_cleans_up(mock_stdio_client, mock_client_session):
    """Test __aexit__ calls necessary cleanup via AsyncExitStack."""
    mock_session_class, mock_session_instance = mock_client_session
    client = MCPClient(VALID_SERVER_CONFIG_DICT)

    async with client:
        assert client.is_active

    mock_stdio_client.return_value.__aexit__.assert_awaited_once()
    mock_session_instance.__aexit__.assert_awaited_once()
    assert not client.is_active
    assert get_client_session(client) is None


# --- Test Cases: Interaction Methods (Success) ---


@pytest.mark.asyncio
async def test_mcp_client_list_tools_success(
    mock_stdio_client,  # noqa: ARG001 Added mock_stdio_client to ensure proper context management
    mock_client_session,
    mock_litellm_mcp_tools,
):
    """Test successful call to list_tools returns OpenAI formatted tools."""
    _, mock_session_instance = (
        mock_client_session  # We need the session for the litellm helper
    )
    expected_openai_tools = [
        ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name="tool1",
                description="desc1",
                parameters={},
            ),
        ),
    ]
    mock_litellm_mcp_tools.load_mcp_tools.return_value = expected_openai_tools

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    async with client:
        actual_result = await client.list_tools()
        mock_litellm_mcp_tools.load_mcp_tools.assert_awaited_once_with(
            session=mock_session_instance,
            format="openai",
        )
        assert actual_result == expected_openai_tools


@pytest.mark.asyncio
async def test_mcp_client_call_tool_success(
    mock_stdio_client,  # noqa: ARG001 Added mock_stdio_client to ensure proper context management
    mock_client_session,
    mock_litellm_mcp_tools,
):
    """Test successful call to call_tool with OpenAI tool call."""
    _, mock_session_instance = (
        mock_client_session  # We need the session for the litellm helper
    )
    tool_call_arg = ChatCompletionMessageToolCall(
        id="call_123",
        function={"name": "test_tool", "arguments": '{"param1": "value1"}'},
        type="function",
    )
    expected_call_tool_result = CallToolResult(
        content=[TextContent(type="text", text="Tool success!")],
    )
    mock_litellm_mcp_tools.call_openai_tool.return_value = expected_call_tool_result

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    async with client:
        actual_result = await client.call_tool(openai_tool_call=tool_call_arg)
        mock_litellm_mcp_tools.call_openai_tool.assert_awaited_once_with(
            session=mock_session_instance,
            openai_tool=tool_call_arg,
        )
        assert actual_result == expected_call_tool_result


# --- Test Cases: Other Interaction Methods (Success, Unchanged) ---
# These methods (list_resources, read_resource, list_prompts) remain largely unchanged
# but we need to adapt the parametrization and fixture usage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "method_name",
        "session_method_name",
        "expected_mcp_result_raw",
        "args",
    ),
    [
        (
            "list_resources",
            "list_resources",
            ListResourcesResult(resources=[Resource(uri=DUMMY_URI, name="n1")]),
            (),
        ),
        (
            "read_resource",
            "read_resource",
            SimpleNamespace(
                contents=[TextContent(type="text", text="data")],
            ),  # ReadResourceResult has no public constructor
            (DUMMY_URI,),
        ),
        (
            "list_prompts",
            "list_prompts",
            SimpleNamespace(prompts=[]),  # ListPromptsResult has no public constructor
            (),
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_stdio_client",
    "mock_litellm_mcp_tools",
)  # Add litellm mock
async def test_mcp_client_other_interaction_methods_success(
    mock_client_session: tuple[MagicMock, AsyncMock],
    method_name: str,
    session_method_name: str,
    expected_mcp_result_raw: object,
    args: tuple,
):
    """Test successful calls to other interaction methods return expected results."""
    _, mock_session_instance = mock_client_session
    session_method_mock = getattr(mock_session_instance, session_method_name)

    # Set the return value for the mocked session method
    session_method_mock.return_value = expected_mcp_result_raw

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    async with client:
        client_method = getattr(client, method_name)
        actual_result = await client_method(*args)

        session_method_mock.assert_awaited_once_with(*args)

        if method_name in ["list_resources", "list_prompts"]:
            # These methods still add "server_name"
            result_list_attr = method_name.split("_")[1]  # "resources" or "prompts"
            # Get items from the raw MCP result
            expected_items_from_raw = getattr(
                expected_mcp_result_raw,
                result_list_attr,
                [],
            )

            assert isinstance(actual_result, list)
            assert len(actual_result) == len(expected_items_from_raw)
            if expected_items_from_raw:
                assert actual_result[0]["server_name"] == client.server_name
                key_field = (
                    "uri" if method_name == "list_resources" else "name"
                )  # prompts don't have name in this structure
                if key_field == "uri":  # Resource has uri
                    assert actual_result[0][key_field] == getattr(
                        expected_items_from_raw[0],
                        key_field,
                    )
                # For prompts, the original items might be Pydantic models, actual_result are dicts
                # We just check server_name and length for prompts for simplicity here
        else:  # read_resource
            assert actual_result == expected_mcp_result_raw


# --- Test Cases: Interaction Methods (Inactive Client) ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("list_tools", ()),
        (
            "call_tool",
            (
                ChatCompletionMessageToolCall(  # Dummy arg for call_tool
                    id="call_inactive",
                    function={"name": "any_tool", "arguments": "{}"},
                    type="function",
                ),
            ),
        ),
        ("list_resources", ()),
        ("read_resource", (DUMMY_URI,)),
        ("list_prompts", ()),
    ],
)
async def test_mcp_client_interaction_methods_inactive(method_name: str, args: tuple):
    """Test calling interaction methods when client is inactive raises MCPClientError."""
    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    client_method = getattr(client, method_name)

    expected_error_msg = f"Client '{client.server_name}' is not connected."
    with pytest.raises(MCPClientError, match=re.escape(expected_error_msg)):
        await client_method(*args)


# --- Test Cases: Interaction Methods (Errors from litellm/session) ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "method_name",
        "litellm_mock_method_name",  # For list_tools, call_tool
        "session_method_name",  # For others
        "error_to_raise",
        "expected_exception_type",
        "expected_match_pattern",
        "args_for_client_method",
    ),
    [
        # list_tools errors (from litellm_mcp_tools.load_mcp_tools)
        (
            "list_tools",
            "load_mcp_tools",
            None,
            McpError(MOCK_MCP_ERROR_OBJ),
            MCPClientInteractionError,
            r"MCP protocol error listing tools for 'test_server'",
            (),
        ),
        (
            "list_tools",
            "load_mcp_tools",
            None,
            ConnectionAbortedError("Net error for list_tools"),
            MCPClientInteractionError,
            r"Failed to list tools for 'test_server'",
            (),
        ),
        # call_tool errors (from litellm_mcp_tools.call_openai_tool)
        (
            "call_tool",
            "call_openai_tool",
            None,
            McpError(MOCK_MCP_ERROR_OBJ),
            MCPClientInteractionError,
            r"MCP protocol error calling tool 'error_tool_name' on 'test_server'",
            (
                ChatCompletionMessageToolCall(
                    id="err_call",
                    function={"name": "error_tool_name", "arguments": "{}"},
                    type="function",
                ),
            ),
        ),
        (
            "call_tool",
            "call_openai_tool",
            None,
            TimeoutError("Timeout for call_tool"),
            MCPClientInteractionError,
            r"Failed to call tool 'error_tool_name_timeout' on 'test_server'",
            (
                ChatCompletionMessageToolCall(
                    id="err_call_timeout",
                    function={"name": "error_tool_name_timeout", "arguments": "{}"},
                    type="function",
                ),
            ),
        ),
        # read_resource errors (from session.read_resource)
        (
            "read_resource",
            None,
            "read_resource",
            McpError(MOCK_MCP_ERROR_OBJ),
            MCPClientInteractionError,
            r"MCP protocol error reading resource 'dummy://server/resource1' from 'test_server'",
            (DUMMY_URI,),
        ),
    ],
)
@pytest.mark.usefixtures("mock_stdio_client")  # Keep for context
async def test_mcp_client_interaction_methods_errors(  # noqa: PLR0913
    mock_client_session: tuple[MagicMock, AsyncMock],
    mock_litellm_mcp_tools: MagicMock,  # Add this
    method_name: str,
    litellm_mock_method_name: str | None,
    session_method_name: str | None,
    error_to_raise: Exception,
    expected_exception_type: type[Exception],
    expected_match_pattern: str,
    args_for_client_method: tuple,
):
    """Test MCPClientInteractionError is raised for underlying errors."""
    _, mock_session_instance = mock_client_session

    if litellm_mock_method_name:  # For list_tools and call_tool
        mock_to_configure = getattr(mock_litellm_mcp_tools, litellm_mock_method_name)
    elif session_method_name:  # For other methods like read_resource
        mock_to_configure = getattr(mock_session_instance, session_method_name)
    else:
        pytest.fail(
            "Either litellm_mock_method_name or session_method_name must be provided",
        )

    mock_to_configure.side_effect = error_to_raise

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    async with client:
        client_method_to_call = getattr(client, method_name)
        with pytest.raises(expected_exception_type, match=expected_match_pattern):
            await client_method_to_call(*args_for_client_method)

        # Verify the mock that was supposed to be called
        if litellm_mock_method_name:
            if litellm_mock_method_name == "load_mcp_tools":
                mock_to_configure.assert_awaited_once_with(
                    session=mock_session_instance,
                    format="openai",
                )
            elif litellm_mock_method_name == "call_openai_tool":
                mock_to_configure.assert_awaited_once_with(
                    session=mock_session_instance,
                    openai_tool=args_for_client_method[0],
                )
        elif session_method_name:
            mock_to_configure.assert_awaited_once_with(*args_for_client_method)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_stdio_client")  # Keep for context
async def test_mcp_client_call_tool_server_error_response(
    mock_client_session: tuple[MagicMock, AsyncMock],  # Keep for context
    mock_litellm_mcp_tools: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test call_tool logs warning when the server returns an error in the result (via litellm helper)."""
    _, _ = (
        mock_client_session  # Unused but part of fixture setup if needed for session access
    )

    tool_name = "error_tool_server_side"
    tool_args_str = '{"a": 1}'
    tool_call_arg = ChatCompletionMessageToolCall(
        id="call_server_err",
        function={"name": tool_name, "arguments": tool_args_str},
        type="function",
    )

    error_result_from_server = CallToolResult(
        isError=True,
        content=[TextContent(type="text", text="Server failed processing")],
    )
    mock_litellm_mcp_tools.call_openai_tool.return_value = error_result_from_server

    client = MCPClient(VALID_SERVER_CONFIG_DICT)
    async with client:
        result = await client.call_tool(openai_tool_call=tool_call_arg)

        assert result == error_result_from_server
        mock_litellm_mcp_tools.call_openai_tool.assert_awaited_once_with(
            session=get_client_session(client),  # Get the actual session instance
            openai_tool=tool_call_arg,
        )

        assert f"Tool '{tool_name}' reported an error" in caplog.text
        assert "Server failed processing" in caplog.text
