"""MCP Client Manager implementation for handling multiple MCP servers."""

import asyncio
import logging
import pathlib  # Use pathlib instead of os.path
from types import TracebackType
from typing import Any, ClassVar, Literal  # Added List

import yaml

# Import types for new methods
from litellm.types.utils import ChatCompletionMessageToolCall
from mcp.types import CallToolResult
from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel, Field, ValidationError, model_validator

# Import the new MCPClient
from streetrace.mcp.client import (
    MCPClient,
    MCPClientConnectionError,
    MCPClientInteractionError,  # Added
)

# Use module-level logger
logger = logging.getLogger(__name__)

# Use pathlib.Path for default path
DEFAULT_CONFIG_PATH: pathlib.Path = (
    pathlib.Path.home() / ".streetrace" / "mcp_servers.yaml"
)

# Define supported transport types
SupportedTransport = Literal["stdio"]


class MCPServerConfig(BaseModel):
    """Pydantic model for validating individual MCP server configurations."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    transport: SupportedTransport = "stdio"

    # Class variable to store seen names during validation across multiple configs
    _seen_names: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def check_transport_and_disable(self) -> "MCPServerConfig":
        """Disable the server if the transport is not 'stdio'."""
        # Combine nested if (SIM102)
        if self.transport != "stdio" and self.enabled:
            logger.warning(
                "[MCPClientManager] Server '%s' uses unsupported transport '%s'. Disabling.",
                self.name,
                self.transport,
            )
            self.enabled = False
        return self


class MCPManagerError(Exception):
    """Base exception for MCPClientManager errors."""


class MCPManagerClientNotFoundError(MCPManagerError):
    """Error when a specific MCP client is not found or is inactive."""


class MCPConfigError(MCPManagerError):
    """Error related to MCP configuration loading or validation."""


class MCPClientManager:
    """Manages the lifecycle of multiple MCPClient instances based on configuration.

    Acts as an asynchronous context manager to start and stop all configured clients.
    """

    def __init__(self, config_path: str | pathlib.Path = DEFAULT_CONFIG_PATH) -> None:
        """Initialize the MCPClientManager by loading server configurations.

        Args:
            config_path: Path to the MCP server configuration YAML file.

        """
        self._config_path: pathlib.Path = pathlib.Path(config_path).expanduser()
        self._config: list[MCPServerConfig] = []
        self._active_clients: dict[str, MCPClient] = {}
        self._load_config()

    # --- Configuration Loading and Validation (Helper Methods for Complexity C901) ---

    def _read_yaml_config(self) -> list[dict[str, Any]]:
        """Read and perform basic structure check on the YAML config file."""
        if not self._config_path.exists():
            logger.warning(
                "[MCPClientManager] Configuration file not found at %s.",
                self._config_path,
            )
            return []

        try:
            with self._config_path.open(encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if (
                not config_data
                or "servers" not in config_data
                or not isinstance(config_data.get("servers"), list)
            ):
                logger.warning(
                    "[MCPClientManager] Config file at %s is empty or invalid format (missing 'servers' list).",
                    self._config_path,
                )
                return []
            return config_data["servers"]

        except yaml.YAMLError as e:
            logger.exception(
                "[MCPClientManager] Error parsing config file %s",
                self._config_path,
            )
            err_msg = f"Error parsing YAML file {self._config_path}: {e}"
            raise MCPConfigError(err_msg) from e
        except OSError as e:
            logger.exception(
                "[MCPClientManager] Error reading config file %s",
                self._config_path,
            )
            err_msg = f"Error reading file {self._config_path}: {e}"
            raise MCPConfigError(err_msg) from e
        except Exception as e:
            logger.exception(
                "[MCPClientManager] Unexpected error reading raw config from %s",
                self._config_path,
            )
            err_msg = f"Unexpected error reading raw config: {e}"
            raise MCPConfigError(err_msg) from e

    def _validate_server_list(
        self,
        raw_server_configs: list[dict[str, Any]],
    ) -> list[MCPServerConfig]:
        """Validate a list of raw server configs using Pydantic and check duplicates."""
        validated_models: list[MCPServerConfig] = []
        seen_names: set[str] = set()

        for i, raw_cfg in enumerate(raw_server_configs):
            if not isinstance(raw_cfg, dict):
                logger.warning(
                    "[MCPClientManager] Skipping invalid config index %d: Item is not a dictionary.",
                    i,
                )
                continue
            try:
                server_model = MCPServerConfig(**raw_cfg)
                if server_model.name in seen_names:
                    logger.warning(
                        "[MCPClientManager] Skipping config index %d: duplicate name '%s'.",
                        i,
                        server_model.name,
                    )
                    continue
                validated_models.append(server_model)
                seen_names.add(server_model.name)
                logger.debug(
                    "[MCPClientManager] Validated config for: %s",
                    server_model.name,
                )
            except ValidationError as e:
                logger.warning(
                    "[MCPClientManager] Skipping invalid config index %d ('%s'): %s",
                    i,
                    raw_cfg.get("name", "N/A"),
                    e,
                )
            except Exception:  # Catch other model instantiation errors
                logger.exception(
                    "[MCPClientManager] Unexpected error validating config index %d ('%s').",
                    i,
                    raw_cfg.get("name", "N/A"),
                )
        return validated_models

    def _load_config(self) -> None:
        """Load and validate the MCP server configuration file using Pydantic."""
        logger.info(
            "[MCPClientManager] Loading MCP server configuration from: %s",
            self._config_path,
        )
        raw_configs = self._read_yaml_config()
        if not raw_configs:
            self._config = []
            logger.info(
                "[MCPClientManager] No raw server configurations found or file empty/invalid.",
            )
            return

        self._config = self._validate_server_list(raw_configs)
        logger.info(
            "[MCPClientManager] Loaded %d valid, unique, and enabled MCP server configurations.",
            len(self.get_enabled_servers()),
        )

    # --- Context Management (__aenter__ / __aexit__) ---

    def _prepare_client_start_tasks(
        self,
        enabled_configs: list[MCPServerConfig],
    ) -> tuple[list[asyncio.Task], dict[int, tuple[str, MCPClient]]]:
        """Create MCPClient instances and tasks to start them."""
        client_tasks = []
        config_map = {}
        for i, config_model in enumerate(enabled_configs):
            server_name = config_model.name
            try:
                client = MCPClient(config_model.model_dump())
                config_map[i] = (server_name, client)
                client_tasks.append(
                    asyncio.create_task(client.__aenter__()),
                )
            except (ValueError, TypeError):
                logger.exception(
                    "[MCPClientManager] Skipping client init for '%s' due to config error.",
                    server_name,
                )
            except Exception:
                logger.exception(
                    "[MCPClientManager] Unexpected error creating client for '%s'",
                    server_name,
                )
        return client_tasks, config_map

    def _process_client_start_results(
        self,
        results: list[Any],
        config_map: dict[int, tuple[str, MCPClient]],
    ) -> int:
        """Process the results of starting MCP clients."""
        successful_initializations = 0
        for i, result in enumerate(results):
            if i not in config_map:
                logger.error(
                    "[MCPClientManager] Result index %d out of bounds for config map.",
                    i,
                )
                continue

            server_name, client_instance = config_map[i]
            if isinstance(result, MCPClientConnectionError):
                logger.error(
                    "[MCPClientManager] Failed to initialize client for server '%s'. Error: %s",
                    server_name,
                    result,
                )
            elif isinstance(result, Exception):
                logger.error(
                    "[MCPClientManager] Unexpected error initializing client for server '%s': %s",
                    server_name,
                    result,
                    exc_info=result,  # Include stack trace for unexpected general exceptions
                )
            elif isinstance(
                result,
                type(client_instance),
            ):  # Check against the type of the *stored* client instance
                logger.info(
                    "[MCPClientManager] Successfully initialized client for server '%s'.",
                    server_name,
                )
                self._active_clients[server_name] = result
                successful_initializations += 1
            else:
                logger.error(
                    "[MCPClientManager] Unexpected result type (%s) during client initialization for '%s'.",
                    type(result).__name__,
                    server_name,
                )
        return successful_initializations

    async def __aenter__(self) -> "MCPClientManager":
        """Enter the async context: Creates and starts MCPClient instances."""
        logger.info("[MCPClientManager] Entering context - initializing clients...")
        enabled_configs = self.get_enabled_servers()
        self._active_clients = {}

        if not enabled_configs:
            logger.info("[MCPClientManager] No enabled servers to initialize.")
            return self

        client_tasks, config_map = self._prepare_client_start_tasks(enabled_configs)

        if not client_tasks:
            logger.info("[MCPClientManager] No client start tasks prepared.")
            return self

        results = await asyncio.gather(*client_tasks, return_exceptions=True)
        successful_initializations = self._process_client_start_results(
            results,
            config_map,
        )

        logger.info(
            "[MCPClientManager] Finished client initialization. %d clients active out of %d attempted.",
            successful_initializations,
            len(config_map),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context: Stops all active MCPClient instances."""
        logger.info(
            "[MCPClientManager] Exiting context - shutting down %d active clients...",
            len(self._active_clients),
        )
        if not self._active_clients:
            return

        client_list = list(self._active_clients.values())
        shutdown_tasks = [
            client.__aexit__(exc_type, exc_val, exc_tb) for client in client_list
        ]
        results = await asyncio.gather(*shutdown_tasks, return_exceptions=True)

        self._active_clients = {}

        for i, result in enumerate(results):
            if i < len(client_list):  # Check bounds
                client_name = client_list[i].server_name
                if isinstance(result, Exception):
                    logger.error(
                        "[MCPClientManager] Error during shutdown of client '%s': %s",
                        client_name,
                        result,
                    )
                else:
                    logger.info(
                        "[MCPClientManager] Client '%s' shutdown completed.",
                        client_name,
                    )
            else:
                logger.error(  # Should not happen if lists are managed correctly
                    "[MCPClientManager] Mismatch between shutdown results and client list index %d",
                    i,
                )
        logger.info("[MCPClientManager] Finished shutting down clients.")

    # --- Public Accessor Methods ---

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get the validated configurations for servers marked as enabled."""
        return [cfg for cfg in self._config if cfg.enabled]

    def get_client(self, server_name: str) -> MCPClient | None:
        """Retrieve an active MCPClient instance by its server name."""
        return self._active_clients.get(server_name)

    def get_active_clients(self) -> dict[str, MCPClient]:
        """Get a dictionary of all currently active MCPClient instances."""
        return self._active_clients.copy()

    def list_active_client_names(self) -> list[str]:
        """List the names of the currently active clients."""
        return list(self._active_clients.keys())

    def get_server_configs(self) -> list[MCPServerConfig]:
        """Get the list of all validated MCPServerConfig objects loaded by the manager."""
        return self._config[:]

    # --- New/Updated Tool Interaction Methods ---

    async def list_all_tools(self) -> list[ChatCompletionToolParam]:
        """List all tools from all active MCP clients in OpenAI format.

        Returns:
            A list of ChatCompletionToolParam objects.

        """
        all_tools: list[ChatCompletionToolParam] = []
        active_clients = self.get_active_clients()  # Get a copy

        if not active_clients:
            logger.info("[MCPClientManager] No active clients to list tools from.")
            return []

        logger.info(
            "[MCPClientManager] Listing tools from %d active clients...",
            len(active_clients),
        )

        for server_name, client in active_clients.items():
            try:
                logger.debug(
                    "[MCPClientManager] Listing tools for client: %s",
                    server_name,
                )
                client_tools: list[ChatCompletionToolParam] = await client.list_tools()
                # Note: server_name is not explicitly added here as
                # litellm's transform_mcp_tool_to_openai_tool does not include it.
                # If server context is needed, tool names themselves should be unique
                # or include server identifiers, or the description field could be used.
                all_tools.extend(client_tools)
                logger.debug(
                    "[MCPClientManager] Found %d tools for client %s",
                    len(client_tools),
                    server_name,
                )
            except (
                MCPClientInteractionError
            ):  # TRY400: Changed from as e and logger.error to logger.exception
                logger.exception(
                    "[MCPClientManager] Error listing tools for client '%s'.",
                    server_name,
                )
            except Exception:  # Catch any other unexpected error
                logger.exception(
                    "[MCPClientManager] Unexpected error listing tools for client '%s'",
                    server_name,
                )
        logger.info(
            "[MCPClientManager] Aggregated %d tools from all active clients.",
            len(all_tools),
        )
        return all_tools

    async def call_tool_on_client(
        self,
        server_name: str,
        openai_tool_call: ChatCompletionMessageToolCall,
    ) -> CallToolResult:
        """Call a tool on a specific active MCP client.

        Args:
            server_name: The name of the server (client) on which to call the tool.
            openai_tool_call: The OpenAI tool call object.

        Returns:
            The result of the tool call.

        Raises:
            MCPManagerClientNotFoundError: If the specified client is not found or inactive.
            MCPClientInteractionError: If the tool call on the client fails.

        """
        client = self.get_client(server_name)
        if not client or not client.is_active:
            msg = f"Client '{server_name}' not found or is not active."
            logger.warning("[MCPClientManager] %s", msg)
            raise MCPManagerClientNotFoundError(msg)

        tool_name_for_log = openai_tool_call.function.name
        logger.info(
            "[MCPClientManager] Relaying tool call '%s' to client '%s'.",
            tool_name_for_log,
            server_name,
        )
        try:
            # MCPClient.call_tool now expects ChatCompletionMessageToolCall
            return await client.call_tool(openai_tool_call=openai_tool_call)
        except (
            MCPClientInteractionError
        ):  # TRY400: Changed from as e and logger.error to logger.exception
            # Client already logs exception details.
            logger.exception(
                "[MCPClientManager] Interaction error from client '%s' for tool '%s'.",
                server_name,
                tool_name_for_log,
            )
            raise  # Re-raise to signal failure to the caller
        except Exception as e:
            logger.exception(
                "[MCPClientManager] Unexpected error calling tool '%s' on client '%s'.",
                tool_name_for_log,
                server_name,
            )
            # Wrap unexpected errors in a standard error type if desired,
            # or re-raise as is. For now, re-raising.
            msg = f"Unexpected error during tool call relay to '{server_name}': {e!s}"
            raise MCPManagerError(msg) from e
