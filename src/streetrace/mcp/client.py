"""MCP Client implementation for managing connection to a single MCP server."""

import contextlib
import logging
from types import TracebackType
from typing import Any  # Added List

from litellm.experimental_mcp_client import tools as litellm_mcp_tools
from litellm.types.utils import ChatCompletionMessageToolCall
from mcp import ClientSession, McpError, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CallToolResult,
    ListPromptsResult,
    ListResourcesResult,
    # ListToolsResult, # No longer directly used here
    ReadResourceResult,
)
from openai.types.chat import ChatCompletionToolParam

# Use module-level logger
logger = logging.getLogger(__name__)

EXPECTED_TRANSPORT_TUPLE_LENGTH = 2


class MCPClientError(Exception):
    """Base exception for MCPClient errors."""


class MCPClientConnectionError(MCPClientError):
    """Error during connection or initialization of an MCPClient."""


class MCPClientInteractionError(MCPClientError):
    """Error during interaction (tool call, resource read) with an MCP server."""


class MCPClient:
    """Manages the connection and interaction lifecycle for a single MCP server.

    Acts as an asynchronous context manager, leveraging `mcp.client.stdio.stdio_client`
    to handle the server subprocess lifecycle.
    """

    def __init__(self, server_config: dict[str, Any]) -> None:
        """Initialize the client for a specific server configuration.

        Args:
            server_config: A dictionary containing the configuration for one server,
                           expected to have keys like 'name', 'command', 'args'.
                           Optional keys include 'env'.

        Raises:
            ValueError: If the server config is missing required keys.

        """
        if not all(k in server_config for k in ["name", "command", "args"]):
            msg = "Server config must include 'name', 'command', and 'args'."
            raise ValueError(msg)

        self.server_name: str = server_config["name"]
        self._config: dict[str, Any] = server_config
        self._session: ClientSession | None = None
        self._exit_stack = contextlib.AsyncExitStack()

    @property
    def is_active(self) -> bool:
        """Check if the client session is established."""
        return self._session is not None

    async def __aenter__(self) -> "MCPClient":
        """Enter the async context: starts the server and initializes the MCP session.

        Uses `mcp.client.stdio.stdio_client` to manage the server process and streams,
        and `mcp.ClientSession` to manage the MCP communication protocol.

        Raises:
            MCPClientConnectionError: If connection or initialization fails.

        """
        logger.info(
            "[MCPClient:%s] Entering context and connecting...",
            self.server_name,
        )
        self._session = None
        self._exit_stack = contextlib.AsyncExitStack()

        try:
            command = self._config["command"]
            args = self._config["args"]
            env_config = self._config.get("env")

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env_config,
            )
            logger.info(
                "[MCPClient:%s] Attempting to start server and connect via stdio_client...",
                self.server_name,
            )

            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params),
            )

            if (
                stdio_transport is None
                or len(stdio_transport) != EXPECTED_TRANSPORT_TUPLE_LENGTH
            ):
                msg = f"stdio_client returned invalid transport streams for {self.server_name}"
                raise MCPClientConnectionError(msg)  # noqa: TRY301

            read_stream, write_stream = stdio_transport

            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )

            logger.info(
                "[MCPClient:%s] Initializing MCP session...",
                self.server_name,
            )
            await session.initialize()
            self._session = session
            logger.info(
                "[MCPClient:%s] Session initialized successfully.",
                self.server_name,
            )

        except FileNotFoundError as e:
            logger.exception(
                "[MCPClient:%s] Command not found: %s",
                self.server_name,
                self._config.get("command", "N/A"),
            )
            await self._exit_stack.aclose()
            msg = f"Command not found for server '{self.server_name}': {self._config.get('command', 'N/A')}"
            raise MCPClientConnectionError(msg) from e
        except McpError as e:
            logger.exception(
                "[MCPClient:%s] MCP error during session initialization.",
                self.server_name,
            )
            await self._exit_stack.aclose()
            msg = f"MCP protocol error connecting client '{self.server_name}': {e}"
            raise MCPClientConnectionError(msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClient:%s] Failed to start server or initialize session.",
                self.server_name,
            )
            await self._exit_stack.aclose()
            msg = f"Failed to connect client '{self.server_name}': {e!s}"
            raise MCPClientConnectionError(msg) from e

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit the async context, closing the session and terminating the server process."""
        logger.info(
            "[MCPClient:%s] Exiting context and disconnecting (via AsyncExitStack)...",
            self.server_name,
        )
        self._session = None
        return await self._exit_stack.aclose()

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """List the tools available on this specific MCP server in OpenAI format.

        Raises:
            MCPClientError: If the client is not connected.
            MCPClientInteractionError: If the server interaction fails.

        """
        if not self.is_active or not self._session:
            msg = f"Client '{self.server_name}' is not connected."
            raise MCPClientError(msg)
        try:
            logger.debug(
                "[MCPClient:%s] Listing tools (OpenAI format)...",
                self.server_name,
            )
            # load_mcp_tools fetches tools and converts them to OpenAI format
            openai_tools: list[ChatCompletionToolParam] = (
                await litellm_mcp_tools.load_mcp_tools(
                    session=self._session,
                    format="openai",
                )
            )
        except McpError as e:
            logger.exception(
                "[MCPClient:%s] MCP protocol error listing tools.",
                self.server_name,
            )
            msg = f"MCP protocol error listing tools for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClient:%s] Error listing tools.",
                self.server_name,
            )
            msg = f"Failed to list tools for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        else:
            return openai_tools  # TRY300: Moved to else block

    async def call_tool(
        self,
        openai_tool_call: ChatCompletionMessageToolCall,
    ) -> CallToolResult:
        """Call a specific tool on this MCP server using OpenAI tool call format.

        Args:
            openai_tool_call: The OpenAI tool call object.

        Raises:
            MCPClientError: If the client is not connected.
            MCPClientInteractionError: If the server interaction fails.

        """
        if not self.is_active or not self._session:
            msg = f"Client '{self.server_name}' is not connected."
            raise MCPClientError(msg)

        tool_name_for_log = openai_tool_call.function.name
        # Arguments are a JSON string in ChatCompletionMessageToolCall.function.arguments
        arguments_for_log = openai_tool_call.function.arguments

        logger.info(
            "[MCPClient:%s] Calling tool '%s' with OpenAI style args: %s",
            self.server_name,
            tool_name_for_log,
            arguments_for_log,
        )
        try:
            # call_openai_tool handles the transformation from OpenAI format
            # to MCP format and calls the tool.
            result: CallToolResult = await litellm_mcp_tools.call_openai_tool(
                session=self._session,
                openai_tool=openai_tool_call,
            )
        except McpError as e:
            logger.exception(
                "[MCPClient:%s] MCP protocol error calling tool '%s'.",
                self.server_name,
                tool_name_for_log,
            )
            msg = f"MCP protocol error calling tool '{tool_name_for_log}' on '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClient:%s] Error calling tool '%s'.",
                self.server_name,
                tool_name_for_log,
            )
            msg = f"Failed to call tool '{tool_name_for_log}' on '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        else:
            if result.isError:
                error_content = getattr(result, "content", None)
                logger.warning(
                    "[MCPClient:%s] Tool '%s' reported an error: %s",
                    self.server_name,
                    tool_name_for_log,
                    error_content or "No details provided",
                )
            else:
                logger.info(
                    "[MCPClient:%s] Tool '%s' call completed successfully.",
                    self.server_name,
                    tool_name_for_log,
                )
            return result

    async def list_resources(self) -> list[dict[str, Any]]:
        """List the resource patterns available on this specific MCP server.

        Raises:
            MCPClientError: If the client is not connected.
            MCPClientInteractionError: If the server interaction fails.

        """
        if not self.is_active or not self._session:
            msg = f"Client '{self.server_name}' is not connected."
            raise MCPClientError(msg)
        try:
            logger.debug("[MCPClient:%s] Listing resources...", self.server_name)
            result: ListResourcesResult | None = await self._session.list_resources()
            resources = result.resources if result else []
            # Add server name context for registry aggregation
        except McpError as e:  # Catch specific MCP errors
            logger.exception(
                "[MCPClient:%s] MCP protocol error listing resources.",
                self.server_name,
            )
            msg = f"MCP protocol error listing resources for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        except Exception as e:  # Catch other potential errors (network, etc.)
            logger.exception(
                "[MCPClient:%s] Error listing resources.",
                self.server_name,
            )
            msg = f"Failed to list resources for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        else:
            return [
                {
                    # Use model_dump for Pydantic v2+, fallback for older/other objects
                    **(res.model_dump() if hasattr(res, "model_dump") else vars(res)),
                    "server_name": self.server_name,
                }
                for res in resources
            ]

    async def read_resource(self, resource_uri: str) -> ReadResourceResult:
        """Read a resource from this specific MCP server.

        Raises:
            MCPClientError: If the client is not connected.
            MCPClientInteractionError: If the server interaction fails.

        """
        if not self.is_active or not self._session:
            msg = f"Client '{self.server_name}' is not connected."
            raise MCPClientError(msg)

        logger.info(
            "[MCPClient:%s] Reading resource: %s",
            self.server_name,
            resource_uri,
        )
        try:
            result: ReadResourceResult = await self._session.read_resource(
                resource_uri,
            )
        except McpError as e:
            logger.exception(
                "[MCPClient:%s] MCP protocol error reading resource '%s'.",
                self.server_name,
                resource_uri,
            )
            msg = f"MCP protocol error reading resource '{resource_uri}' from '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClient:%s] Error reading resource '%s'.",
                self.server_name,
                resource_uri,
            )
            msg = f"Failed to read resource '{resource_uri}' from '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        else:  # ref TRY300
            logger.info(
                "[MCPClient:%s] Resource '%s' read successfully.",
                self.server_name,
                resource_uri,
            )
            return result

    async def list_prompts(self) -> list[dict[str, Any]]:
        """List the prompts available on this specific MCP server.

        Raises:
            MCPClientError: If the client is not connected.
            MCPClientInteractionError: If the server interaction fails.

        """
        if not self.is_active or not self._session:
            msg = f"Client '{self.server_name}' is not connected."
            raise MCPClientError(msg)
        try:
            logger.debug("[MCPClient:%s] Listing prompts...", self.server_name)
            result: ListPromptsResult | None = await self._session.list_prompts()
            prompts = result.prompts if result else []
        except McpError as e:
            logger.exception(
                "[MCPClient:%s] MCP protocol error listing prompts.",
                self.server_name,
            )
            msg = f"MCP protocol error listing prompts for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClient:%s] Error listing prompts.",
                self.server_name,
            )
            msg = f"Failed to list prompts for '{self.server_name}'."
            raise MCPClientInteractionError(msg) from e
        else:
            return [
                {
                    **(p.model_dump() if hasattr(p, "model_dump") else vars(p)),
                    "server_name": self.server_name,
                }
                for p in prompts
            ]

    # Add get_prompt if needed, mirroring list_prompts structure
