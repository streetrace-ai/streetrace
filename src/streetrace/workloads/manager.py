"""Workload manager for the StreetRace application.

This module implements location-first workload discovery and loading.
WorkloadManager is renamed from AgentManager to reflect the true abstraction:
StreetRace runs Supervisor which supervises Workloads.

Workload Discovery Flow:
+-------------------------------------------------------------+
| User provides: --agent=IDENTIFIER                           |
+-------------------------------------------------------------+
                          |
                          v
              +---------------------+
              | Is it an HTTP URL?  |
              +---------------------+
                    |           |
                   Yes          No
                    |           |
                    v           v
            +----------+  +----------------+
            |Load from |  |Is it a path?   |
            |  HTTP    |  +----------------+
            +----------+       |      |
                              Yes     No
                               |      |
                               v      v
                        +----------+ +-----------------+
                        |Load from | |Search by name:  |
                        |  path    | |1. cwd           |
                        +----------+ |2. home          |
                                     |3. bundled       |
                                     +-----------------+
                                            |
                                            v
                                  +----------------------+
                                  |Within each location: |
                                  |Try all formats       |
                                  |(YAML, Python, DSL)   |
                                  |First match wins      |
                                  +----------------------+

Location Priority:
1. Current working directory (./agents, .streetrace/agents)
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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from opentelemetry import trace

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.session.session_manager import SessionManager

# Import DSL compiler exceptions for error handling
from streetrace.agents.base_agent_loader import AgentValidationError
from streetrace.agents.resolver import SourceResolver
from streetrace.dsl.compiler import DslSemanticError, DslSyntaxError
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.workloads.definition import WorkloadDefinition
from streetrace.workloads.dsl_loader import DslDefinitionLoader
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.protocol import Workload
from streetrace.workloads.python_loader import PythonDefinitionLoader
from streetrace.workloads.yaml_loader import YamlDefinitionLoader

logger = get_logger(__name__)

_DEFAULT_AGENT = "Streetrace_Coding_Agent"
"""Default agent name used when 'default' is specified."""


class WorkloadNotFoundError(Exception):
    """Raised when a workload definition cannot be found by name."""

    def __init__(self, name: str) -> None:
        """Initialize with the workload name that was not found.

        Args:
            name: The name of the workload that could not be found.

        """
        self.name = name
        super().__init__(f"Workload '{name}' not found")


def _set_workload_telemetry_attributes(
    definition: WorkloadDefinition,
    identifier: str,
) -> None:
    """Set telemetry attributes on the current span from workload definition.

    Args:
        definition: The workload definition to extract attributes from
        identifier: The workload identifier (name, path, or URL)

    """
    current_span = trace.get_current_span()
    if current_span is None or not current_span.is_recording():
        return

    from streetrace.version import get_streetrace_version

    # Add workload metadata
    current_span.set_attribute(
        "langfuse.trace.streetrace.workload.name",
        definition.name,
    )
    current_span.set_attribute(
        "langfuse.trace.streetrace.workload.format",
        definition.metadata.format,
    )
    current_span.set_attribute(
        "langfuse.trace.streetrace.workload.identifier",
        identifier,
    )

    # Add source path if available
    if definition.metadata.source_path:
        current_span.set_attribute(
            "langfuse.trace.streetrace.workload.source_path",
            str(definition.metadata.source_path),
        )

    # Add streetrace binary version
    current_span.set_attribute(
        "langfuse.trace.streetrace.binary.version",
        get_streetrace_version(),
    )


class WorkloadManager:
    """Manage workload discovery and creation with location-first priority.

    The WorkloadManager implements location-first workload resolution:
    - For HTTP URLs: Load immediately (YAML only, others rejected for security)
    - For explicit paths: Load from that path (format auto-detected)
    - For workload names: Search locations in order, first match wins (any format)

    Search locations (in priority order):
    1. Current working directory (./agents, .streetrace/agents)
    2. User home directory (~/.streetrace/agents)
    3. Bundled agents (src/streetrace/agents/*/agent.py and *.yaml)

    This class uses only DefinitionLoader instances for loading all formats.
    The old AgentLoader infrastructure has been removed.
    """

    # Search locations in priority order
    # Each entry is (name, relative_paths)
    # Special handling: "bundled" uses __file__ to find agents relative to this module
    SEARCH_LOCATION_SPECS: ClassVar[list[tuple[str, list[str]]]] = [
        ("cwd", ["./agents", ".streetrace/agents"]),
        ("home", ["~/.streetrace/agents"]),
        ("bundled", []),  # Will be computed from __file__ in _compute_search_locations
    ]

    def __init__(  # noqa: PLR0913
        self,
        model_factory: ModelFactory,
        tool_provider: ToolProvider,
        system_context: SystemContext,
        work_dir: Path,
        session_manager: "SessionManager | None" = None,
        http_auth: str | None = None,
    ) -> None:
        """Initialize the WorkloadManager.

        Args:
            model_factory: Factory for creating and managing LLM models
            tool_provider: Provider of tools for the agents
            system_context: System context containing project-level instructions
            work_dir: Current working directory
            session_manager: Session manager for lazy access to session service
            http_auth: Authorization header value for HTTP agent URIs

        """
        self.model_factory = model_factory
        self.tool_provider = tool_provider
        self.system_context = system_context
        self.work_dir = work_dir
        self._session_manager = session_manager
        self.http_auth = http_auth

        # Compute search locations
        self.search_locations = self._compute_search_locations()

        # Definition loaders mapped by file extension or special key
        # Python loader uses "python" key since it handles directories, not extensions
        self._definition_loaders: dict[str, DefinitionLoader] = {
            ".sr": DslDefinitionLoader(),
            ".yaml": YamlDefinitionLoader(http_auth=http_auth),
            ".yml": YamlDefinitionLoader(http_auth=http_auth),
            "python": PythonDefinitionLoader(),
        }

        # Cache for WorkloadDefinition objects (name -> WorkloadDefinition)
        self._definitions: dict[str, WorkloadDefinition] = {}

        # Track errors from last load attempt for better error messages
        self._last_load_errors: list[str] = []

    @property
    def session_service(self) -> "BaseSessionService | None":
        """Get the session service lazily from session manager.

        This property defers the heavy ADK import until the session service
        is actually needed (when creating workloads).

        Returns:
            The session service, or None if session_manager was not provided.

        """
        if self._session_manager is None:
            return None
        return self._session_manager.session_service

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
                # Get the directory where agents are located
                # Bundled agents are in the agents package
                from streetrace import agents

                bundled_path = Path(agents.__file__).parent.resolve()
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

    @asynccontextmanager
    async def create_workload(
        self,
        identifier: str,
    ) -> AsyncGenerator[Workload, None]:
        """Create a runnable workload from identifier.

        This is the main entry point for creating workloads. It loads the
        definition using the appropriate DefinitionLoader and creates a
        workload from it.

        Args:
            identifier: Workload identifier (name, path, or URL)

        Yields:
            The created workload

        Raises:
            ValueError: If workload creation fails

        """
        # Handle "default" alias
        if identifier == "default":
            identifier = _DEFAULT_AGENT

        # Load workload definition using definition loaders
        definition = self._load_definition_from_identifier(identifier)

        if definition is None:
            # Build detailed error message with context
            error_details = (
                "\n".join(f"  - {err}" for err in self._last_load_errors)
                if self._last_load_errors
                else "  - Unknown error during workload loading"
            )
            msg = (
                f"Workload '{identifier}' not found.\n"
                f"Details:\n{error_details}\n"
                f"Try --list-agents to see available workloads."
            )
            raise ValueError(msg)

        # Set telemetry attributes from workload definition
        _set_workload_telemetry_attributes(definition, identifier)

        # Validate session_service is available
        if self.session_service is None:
            msg = "session_service is required to create workloads"
            raise ValueError(msg)

        # Create workload from definition
        workload = definition.create_workload(
            model_factory=self.model_factory,
            tool_provider=self.tool_provider,
            system_context=self.system_context,
            session_service=self.session_service,
        )

        try:
            yield workload
        finally:
            await workload.close()

    def _load_definition_from_identifier(
        self,
        identifier: str,
    ) -> WorkloadDefinition | None:
        """Load workload definition from identifier.

        Routes to the appropriate loading strategy:
        1. HTTP URLs -> YAML loader only (others rejected for security)
        2. File paths -> Appropriate loader based on extension/type
        3. Names -> Discover and load

        Args:
            identifier: Workload identifier (URL, path, or name)

        Returns:
            WorkloadDefinition or None if not found

        """
        # Clear previous errors
        self._last_load_errors = []

        # Case 1: HTTP URL
        if identifier.startswith(("http://", "https://")):
            return self._load_from_url(identifier)

        # Case 2: Explicit file path
        if self._is_file_path(identifier):
            path = Path(identifier).expanduser().resolve()
            return self._load_from_path(path)

        # Case 3: Name lookup via discovery
        return self._load_by_name(identifier)

    def _load_from_url(self, url: str) -> WorkloadDefinition | None:
        """Load workload definition from HTTP URL.

        DSL and YAML are supported for HTTP loading. Python is rejected
        for security reasons (requires code import).

        Args:
            url: HTTP(S) URL

        Returns:
            WorkloadDefinition or None

        """
        # Use SourceResolver to fetch and detect format
        resolver = SourceResolver(http_auth=self.http_auth)
        try:
            resolution = resolver.resolve(url)
        except ValueError as e:
            self._last_load_errors.append(f"Failed to load from {url}: {e}")
            raise

        # Get appropriate loader based on detected format
        loader = self._get_loader_for_format(resolution.format)
        if loader is None:
            msg = f"No loader available for format: {resolution.format}"
            self._last_load_errors.append(msg)
            raise ValueError(msg)

        try:
            return loader.load(resolution)
        except (ValueError, OSError, DslSyntaxError, DslSemanticError) as e:
            self._last_load_errors.append(f"Failed to load from {url}: {e}")
            raise

    def _load_from_path(self, path: Path) -> WorkloadDefinition | None:
        """Load workload definition from file path.

        Uses SourceResolver to read content and detect format.

        Args:
            path: File or directory path

        Returns:
            WorkloadDefinition or None

        """
        # Use SourceResolver to resolve and read the file
        resolver = SourceResolver(http_auth=self.http_auth)
        try:
            resolution = resolver.resolve(str(path))
        except ValueError as e:
            self._last_load_errors.append(f"Failed to resolve {path}: {e}")
            return None

        # Get appropriate loader based on detected format
        loader = self._get_loader_for_format(resolution.format)
        if loader is None:
            self._last_load_errors.append(
                f"No loader available for format: {resolution.format}",
            )
            return None

        try:
            return loader.load(resolution)
        except (
            ValueError,
            FileNotFoundError,
            ImportError,
            DslSyntaxError,
            DslSemanticError,
        ) as e:
            self._last_load_errors.append(f"Failed to load from {path}: {e}")
            return None

    def _load_by_name(self, name: str) -> WorkloadDefinition | None:
        """Load workload definition by name via discovery.

        Discovers all workloads and looks up by name.

        Args:
            name: Workload name

        Returns:
            WorkloadDefinition or None

        """
        # Check cache first
        name_lower = name.lower()
        if name_lower in self._definitions:
            return self._definitions[name_lower]

        # Discover all definitions
        self.discover_definitions()

        # Look up by name (case-insensitive)
        if name_lower in self._definitions:
            logger.info(
                "Loading workload '%s' from discovery cache",
                name,
                extra={"workload_name": name},
            )
            return self._definitions[name_lower]

        # Not found
        searched_locations = [loc_name for loc_name, _ in self.search_locations]
        locations_str = ", ".join(searched_locations)
        self._last_load_errors.append(
            f"Workload '{name}' not found in locations: {locations_str}",
        )
        return None

    def _is_file_path(self, identifier: str) -> bool:
        """Check if identifier looks like a file path.

        Args:
            identifier: Potential file path

        Returns:
            True if identifier appears to be a file path

        """
        return (
            identifier.startswith(("/", "~/", "./", "../"))
            or Path(identifier).exists()
        )

    def discover_definitions(self) -> list[WorkloadDefinition]:
        """Discover and compile all workload definitions.

        Uses the DefinitionLoader system. Compilation happens immediately
        during load(), ensuring invalid files are rejected early.

        Implements location-first priority: for duplicate names, the first
        location wins.

        Returns:
            List of successfully loaded WorkloadDefinition objects

        """
        definitions: list[WorkloadDefinition] = []

        # Track seen names for deduplication (location priority)
        seen_names: set[str] = set()

        # Process locations in priority order
        for location_name, paths in self.search_locations:
            location_defs = self._discover_in_location(paths, seen_names)
            for definition in location_defs:
                name_lower = definition.name.lower()
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    definitions.append(definition)
                    self._definitions[name_lower] = definition
                    logger.debug(
                        "Discovered workload '%s' (%s) in %s",
                        definition.name,
                        definition.metadata.format,
                        location_name,
                    )

        return definitions

    def _discover_in_location(
        self,
        paths: list[Path],
        seen_names: set[str],
    ) -> list[WorkloadDefinition]:
        """Discover workload definitions in specific paths.

        Uses SourceResolver to discover all agents in the given paths,
        then loads each one with the appropriate loader.

        Args:
            paths: Paths to search in
            seen_names: Names already discovered (for deduplication)

        Returns:
            List of discovered WorkloadDefinition objects

        """
        definitions: list[WorkloadDefinition] = []

        # Use SourceResolver to discover all agents in the paths
        resolver = SourceResolver(http_auth=self.http_auth)
        discovered = resolver.discover(paths)

        # Load each discovered resolution
        for name, resolution in discovered.items():
            if name in seen_names:
                continue

            loader = self._get_loader_for_format(resolution.format)
            if loader is None:
                logger.warning(
                    "No loader for format '%s' for %s",
                    resolution.format,
                    resolution.source,
                )
                continue

            try:
                definition = loader.load(resolution)
                definitions.append(definition)
            except (
                ValueError,
                FileNotFoundError,
                OSError,
                SyntaxError,
                DslSyntaxError,
                DslSemanticError,
                ImportError,
                AgentValidationError,
            ) as e:
                logger.warning("Failed to load %s: %s", resolution.source, e)

        return definitions

    def create_workload_from_definition(self, name: str) -> Workload:
        """Create a runnable workload by name using the definition system.

        Args:
            name: The workload name to create

        Returns:
            A Workload instance ready for execution

        Raises:
            WorkloadNotFoundError: If no definition with this name is found

        """
        name_lower = name.lower()
        definition = self._definitions.get(name_lower)

        if definition is None:
            # Try to discover definitions and retry
            self.discover_definitions()
            definition = self._definitions.get(name_lower)

        if definition is None:
            raise WorkloadNotFoundError(name)

        if self.session_service is None:
            msg = "session_service is required to create workloads"
            raise ValueError(msg)

        return definition.create_workload(
            model_factory=self.model_factory,
            tool_provider=self.tool_provider,
            system_context=self.system_context,
            session_service=self.session_service,
        )

    def _find_workload_files(self) -> list[Path]:
        """Find all loadable workload files in search paths.

        Uses SourceResolver to discover all agents in search locations.

        Returns:
            List of paths to loadable workload files

        """
        files: list[Path] = []

        # Flatten search paths for discovery
        all_paths = []
        for _, paths in self.search_locations:
            all_paths.extend(paths)

        # Use SourceResolver to discover all agents
        resolver = SourceResolver(http_auth=self.http_auth)
        discovered = resolver.discover(all_paths)

        # Extract file paths from resolutions
        for resolution in discovered.values():
            if resolution.file_path and resolution.file_path not in files:
                files.append(resolution.file_path)

        return files

    def _get_loader_for_format(self, fmt: str | None) -> DefinitionLoader | None:
        """Get the appropriate definition loader for a format.

        Args:
            fmt: Format string ("dsl", "yaml", "python") or None

        Returns:
            The DefinitionLoader instance for this format, or None if
            no loader can handle this format

        """
        if fmt == "dsl":
            return self._definition_loaders[".sr"]
        if fmt == "yaml":
            return self._definition_loaders[".yaml"]
        if fmt == "python":
            return self._definition_loaders["python"]
        return None

    def _get_definition_loader(self, path: Path) -> DefinitionLoader | None:
        """Get the appropriate definition loader for a file path.

        Args:
            path: Path to the file to load

        Returns:
            The DefinitionLoader instance for this file type, or None if
            no loader can handle this file

        """
        # Check for Python agent directory
        if path.is_dir():
            agent_file = path / "agent.py"
            if agent_file.exists():
                return self._definition_loaders["python"]
            return None

        # Check by file extension
        ext = path.suffix.lower()
        return self._definition_loaders.get(ext)
