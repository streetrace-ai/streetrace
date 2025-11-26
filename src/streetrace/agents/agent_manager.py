"""Agent manager for the StreetRace application.

This module implements location-first agent discovery and loading.

Agent Discovery Flow:
┌─────────────────────────────────────────────────────────────┐
│ User provides: --agent=IDENTIFIER                           │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Is it an HTTP URL?    │
              └───────────────────────┘
                    │           │
                   Yes          No
                    │           │
                    ▼           ▼
            ┌──────────┐  ┌──────────────┐
            │Load from │  │Is it a path? │
            │  HTTP    │  └──────────────┘
            └──────────┘       │      │
                              Yes     No
                               │      │
                               ▼      ▼
                        ┌──────────┐ ┌─────────────────┐
                        │Load from │ │Search by name:  │
                        │  path    │ │1. cwd           │
                        └──────────┘ │2. home          │
                                     │3. bundled       │
                                     └─────────────────┘
                                            │
                                            ▼
                                  ┌──────────────────────┐
                                  │Within each location: │
                                  │Try all formats       │
                                  │(YAML, Python, MD)    │
                                  │First match wins      │
                                  └──────────────────────┘

Location Priority:
1. Current working directory (./agents, ., .streetrace/agents)
2. User home directory (~/.streetrace/agents)
3. Bundled agents (src/streetrace/agents/)

Within each location, the first matching agent (any format) wins.
This allows users to override bundled agents by placing their own in ./agents.

Environment Variables:
- STREETRACE_AGENT_PATHS: Colon-separated list of additional search paths
  (highest priority)
- STREETRACE_AGENT_URI_AUTH: Default authorization for HTTP agent URIs
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from google.adk.agents import BaseAgent

    from streetrace.agents.street_race_agent import StreetRaceAgent


from streetrace.agents.base_agent_loader import AgentInfo, AgentLoader
from streetrace.agents.py_agent_loader import PythonAgentLoader
from streetrace.agents.yaml_agent_loader import YamlAgentLoader
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider

logger = get_logger(__name__)

_DEFAULT_AGENT = "Streetrace_Coding_Agent"


def _set_agent_telemetry_attributes(
    agent_definition: "StreetRaceAgent",
    agent_identifier: str,
) -> None:
    """Set telemetry attributes on the current span from agent definition.

    Args:
        agent_definition: The agent definition to extract attributes from
        agent_identifier: The agent identifier (name, path, or URL)

    """
    from opentelemetry import trace

    current_span = trace.get_current_span()
    if current_span is None or not current_span.is_recording():
        return

    from streetrace.version import get_streetrace_version

    # Add custom attributes from agent definition
    for key, value in agent_definition.get_attributes().items():
        # Prefix with langfuse.trace. if not already present
        if key.startswith("langfuse.trace."):
            prefixed_key = key
        else:
            prefixed_key = f"langfuse.trace.{key}"
        current_span.set_attribute(prefixed_key, value)
        if key == "streetrace.org.id":
            org_id = str(value)
            # set langfuse org id attribute
            current_span.set_attribute("langfuse.trace.tags", [f"org:{org_id}"])

    # Add agent version if available
    agent_version = agent_definition.get_version()
    if agent_version is not None:
        current_span.set_attribute(
            "langfuse.trace.streetrace.agent.version",
            agent_version,
        )

    # Add system prompt if available
    system_prompt = agent_definition.get_system_prompt()
    if system_prompt is not None:
        current_span.set_attribute(
            "langfuse.trace.streetrace.agent.system_prompt",
            system_prompt,
        )

    # Add streetrace-specific attributes
    agent_card = agent_definition.get_agent_card()
    current_span.set_attribute(
        "langfuse.trace.streetrace.agent.name",
        agent_card.name or agent_identifier,
    )

    # Add streetrace binary version
    current_span.set_attribute(
        "langfuse.trace.streetrace.binary.version",
        get_streetrace_version(),
    )


class AgentManager:
    """Manages agent discovery and creation with location-first priority.

    The AgentManager implements location-first agent resolution:
    - For HTTP URLs: Load immediately (format auto-detected)
    - For explicit paths: Load from that path (format auto-detected)
    - For agent names: Search locations in order, first match wins (any format)

    Search locations (in priority order):
    1. Current working directory (./agents, ., .streetrace/agents)
    2. User home directory (~/.streetrace/agents)
    3. Bundled agents (src/streetrace/agents/*/agent.py and *.yaml)
    """

    # Search locations in priority order
    # Each entry is (name, relative_paths)
    # Special handling: "bundled" uses __file__ to find agents relative to this module
    SEARCH_LOCATION_SPECS: ClassVar[list[tuple[str, list[str]]]] = [
        ("cwd", ["./agents", ".", ".streetrace/agents"]),
        ("home", ["~/.streetrace/agents"]),
        ("bundled", []),  # Will be computed from __file__ in _compute_search_locations
    ]

    def __init__(
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
        work_dir: Path,
        http_auth: str | None = None,
    ) -> None:
        """Initialize the AgentManager.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the agents
            system_context: System context containing project-level instructions
            work_dir: Current working directory
            http_auth: Authorization header value for HTTP agent URIs

        """
        self.model_factory = model_factory
        self.tool_provider = tool_provider
        self.system_context = system_context
        self.work_dir = work_dir
        self.http_auth = http_auth

        # Compute search locations
        self.search_locations = self._compute_search_locations()

        # Initialize format loaders
        self.format_loaders: dict[str, AgentLoader] = {
            "yaml": YamlAgentLoader(http_auth=http_auth),
            "python": PythonAgentLoader(),
        }

        # Cache for discovered agents (name -> (location, AgentInfo))
        self._discovery_cache: dict[str, tuple[str, AgentInfo]] | None = None

        # Track errors from last load attempt for better error messages
        self._last_load_errors: list[str] = []

    def _compute_search_locations(self) -> list[tuple[str, list[Path]]]:  # noqa: C901
        """Compute search locations in priority order.

        Supports STREETRACE_AGENT_PATHS environment variable for custom paths.
        Custom paths have highest priority.

        Returns:
            List of (location_name, paths) tuples

        """
        locations = []

        # Check for custom paths from environment variable (highest priority)
        custom_paths_env = os.environ.get("STREETRACE_AGENT_PATHS", "").strip()
        if custom_paths_env:
            custom_paths = [
                Path(p.strip()).expanduser().resolve()
                for p in custom_paths_env.split(":")
                if p.strip()
            ]
            existing_custom = [p for p in custom_paths if p.exists()]
            if existing_custom:
                locations.append(("custom", existing_custom))
                logger.info(
                    "Using custom agent paths from STREETRACE_AGENT_PATHS: %s",
                    existing_custom,
                )

        for name, rel_paths in self.SEARCH_LOCATION_SPECS:
            resolved_paths = []

            # Special handling for bundled agents
            if name == "bundled":
                # Get the directory where this module (agent_manager.py) is located
                # Bundled agents are in the same directory as agent_manager.py
                bundled_path = Path(__file__).parent.resolve()
                if bundled_path.exists():
                    resolved_paths.append(bundled_path)
            else:
                # Handle regular paths
                for rel_path in rel_paths:
                    if rel_path.startswith("/"):
                        # Absolute path
                        path = Path(rel_path)
                    elif rel_path.startswith("~/"):
                        # Home directory
                        path = Path(rel_path).expanduser()
                    else:
                        # Relative to work_dir
                        path = (self.work_dir / rel_path).resolve()

                    if path.exists():
                        resolved_paths.append(path)

            if resolved_paths:
                locations.append((name, resolved_paths))

        return locations

    def discover(self) -> list[AgentInfo]:
        """Discover all known agents with location-first priority.

        For each location, discovers agents of all formats. First match by name wins.

        Returns:
            List of AgentInfo objects (deduplicated by name, location priority)

        """
        if self._discovery_cache is not None:
            return [info for _, info in self._discovery_cache.values()]

        discovered: dict[str, tuple[str, AgentInfo]] = {}

        # Iterate locations in priority order
        for location_name, paths in self.search_locations:
            # Discover from all formats in this location
            location_agents = self._discover_in_location(paths)

            # Add to cache if not already found in higher-priority location
            for agent_info in location_agents:
                name_lower = agent_info.name.lower()
                if name_lower not in discovered:
                    discovered[name_lower] = (location_name, agent_info)
                    logger.debug(
                        "Discovered agent '%s' (%s) in %s",
                        agent_info.name,
                        agent_info.kind,
                        location_name,
                    )

        self._discovery_cache = discovered
        return [info for _, info in discovered.values()]

    def _discover_in_location(self, paths: list[Path]) -> list[AgentInfo]:
        """Discover all agents in given paths (all formats).

        Args:
            paths: Paths to search in

        Returns:
            List of discovered agents

        """
        agents = []

        for format_name, loader in self.format_loaders.items():
            try:
                format_agents = loader.discover_in_paths(paths)
                agents.extend(format_agents)
            except (ValueError, OSError, ImportError) as e:
                logger.debug(
                    "Failed to discover %s agents in %s: %s",
                    format_name,
                    paths,
                    e,
                )

        return agents

    @asynccontextmanager
    async def create_agent(
        self,
        agent_identifier: str,
    ) -> "AsyncGenerator[BaseAgent, None]":
        """Create agent from identifier with location-first priority.

        Resolution order:
        1. If HTTP URL -> load directly (bypasses location priority)
        2. If file path -> load directly from that path
        3. If agent name -> use location-first discovery

        Args:
            agent_identifier: Agent identifier (name, path, or URL)

        Yields:
            The created agent

        Raises:
            ValueError: If agent creation fails

        """
        # Handle "default" alias
        if agent_identifier == "default":
            agent_identifier = _DEFAULT_AGENT

        # Load agent definition
        agent_definition = self._load_agent_definition(agent_identifier)

        if not agent_definition:
            # Build detailed error message with context
            error_details = (
                "\n".join(f"  - {err}" for err in self._last_load_errors)
                if self._last_load_errors
                else "  - Unknown error during agent loading"
            )
            msg = (
                f"Agent '{agent_identifier}' not found.\n"
                f"Details:\n{error_details}\n"
                f"Try --list-agents to see available agents."
            )
            raise ValueError(msg)

        # Set telemetry attributes from agent definition
        _set_agent_telemetry_attributes(agent_definition, agent_identifier)

        # Create and yield agent
        agent: BaseAgent | None = None
        try:
            agent = await agent_definition.create_agent(
                self.model_factory,
                self.tool_provider,
                self.system_context,
            )
            yield agent
        finally:
            if agent:
                await agent_definition.close(agent)

    def _load_agent_definition(self, identifier: str) -> "StreetRaceAgent | None":
        """Load agent definition from identifier with detailed error tracking.

        Args:
            identifier: Agent identifier (name, path, or URL)

        Returns:
            Loaded agent definition or None if not found

        """
        # Clear previous errors
        self._last_load_errors = []

        # Case 1: HTTP URL (bypass location priority)
        if identifier.startswith(("http://", "https://")):
            return self._load_from_http(identifier)

        # Case 2: Explicit file path
        if self._is_file_path(identifier):
            path = Path(identifier)
            return self._load_from_path(path)

        # Case 3: Agent name (use location-first discovery)
        agent = self._load_by_name(identifier)
        if not agent:
            searched_locations = [name for name, _ in self.search_locations]
            self._last_load_errors.append(
                f"Agent '{identifier}' not found in locations: "
                f"{', '.join(searched_locations)}",
            )
        return agent

    def _load_from_http(self, url: str) -> "StreetRaceAgent | None":
        """Load agent from HTTP URL.

        Args:
            url: HTTP(S) URL

        Returns:
            Loaded agent or None if cannot load

        """
        # Try YAML first (most common for HTTP)
        for format_name in ["yaml"]:
            if format_name not in self.format_loaders:
                continue

            loader = self.format_loaders[format_name]
            try:
                return loader.load_from_url(url)
            except ValueError as e:
                logger.debug("Failed to load as %s from %s: %s", format_name, url, e)
                # Store the actual error message for better user feedback
                self._last_load_errors.append(f"Failed to load from {url}: {e}")

        return None

    def _load_from_path(self, path: Path) -> "StreetRaceAgent | None":
        """Load agent from explicit file/directory path with smart format detection.

        Uses file extension hints to try the most likely format first,
        then falls back to trying all formats.

        Args:
            path: File or directory path

        Returns:
            Loaded agent or None if cannot load

        """
        # Define format hints based on file extension
        format_hints: dict[str, list[str]] = {
            ".yaml": ["yaml"],
            ".yml": ["yaml"],
            ".md": ["markdown"],
            ".py": ["python"],
        }

        # Try format based on file extension first (if it's a file)
        if path.is_file():
            ext = path.suffix.lower()
            if ext in format_hints:
                for format_name in format_hints[ext]:
                    if format_name in self.format_loaders:
                        try:
                            agent = self.format_loaders[format_name].load_from_path(
                                path,
                            )
                            logger.debug(
                                "Loaded agent from %s using %s format (extension hint)",
                                path,
                                format_name,
                            )
                        except ValueError as e:
                            logger.debug(
                                "Failed to load as %s from %s: %s",
                                format_name,
                                path,
                                e,
                            )
                            # Store the actual error for better user feedback
                            self._last_load_errors.append(
                                f"Failed to load from {path}: {e}",
                            )
                        else:
                            return agent

        # Fallback: try all formats
        for format_name, loader in self.format_loaders.items():
            try:
                agent = loader.load_from_path(path)
                logger.debug(
                    "Loaded agent from %s using %s format (fallback)",
                    path,
                    format_name,
                )
            except ValueError as e:
                logger.debug("Failed to load as %s from %s: %s", format_name, path, e)
                # Store the actual error for better user feedback
                self._last_load_errors.append(f"Failed to load from {path}: {e}")
            else:
                return agent

        return None

    def _load_by_name(self, name: str) -> "StreetRaceAgent | None":
        """Load agent by name using location-first discovery with observability.

        Args:
            name: Agent name

        Returns:
            Loaded agent or None if not found

        """
        # Ensure discovery has run
        self.discover()

        # Look up in cache (already has location priority)
        name_lower = name.lower()
        if self._discovery_cache and name_lower in self._discovery_cache:
            location, agent_info = self._discovery_cache[name_lower]

            # Log with structured data for observability
            logger.info(
                "Loading agent '%s' (%s) from %s",
                name,
                agent_info.kind,
                location,
                extra={
                    "agent_name": name,
                    "agent_format": agent_info.kind,
                    "agent_location": location,
                    "agent_path": (
                        str(agent_info.file_path) if agent_info.file_path else None
                    ),
                },
            )

            # Load using the appropriate format loader
            format_loader = self.format_loaders[agent_info.kind]
            return format_loader.load_agent(agent_info)

        return None

    def _is_file_path(self, identifier: str) -> bool:
        """Check if identifier looks like a file path.

        Args:
            identifier: Potential file path

        Returns:
            True if identifier appears to be a file path

        """
        return (
            identifier.startswith(("/", "~/", "./", "../")) or Path(identifier).exists()
        )
