"""YAML agent loader with validation and reference resolution."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from streetrace.agents.street_race_agent import StreetRaceAgent

import yaml
from pydantic import ValidationError

from streetrace.agents.base_agent_loader import (
    AgentCycleError,
    AgentInfo,
    AgentLoader,
    AgentValidationError,
)
from streetrace.agents.resolver import AgentResolver
from streetrace.agents.yaml_models import (
    AgentRef,
    InlineAgentSpec,
    ToolSpec,
    YamlAgentDocument,
    YamlAgentSpec,
)
from streetrace.log import get_logger
from streetrace.utils.file_discovery import find_files

logger = get_logger(__name__)

# Maximum depth for $ref resolution to prevent infinite recursion
MAX_REF_DEPTH = 5


def _parse_yaml_string(content: str, source: str) -> dict[str, Any]:
    """Parse YAML content from string.

    Args:
        content: YAML content as string
        source: Source identifier for error messages

    Returns:
        Parsed YAML data as dict

    Raises:
        AgentValidationError: If parsing fails

    """
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            msg = f"YAML must contain a mapping/object, got {type(data).__name__}"
            raise AgentValidationError(msg)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML syntax in {source}: {e}"
        raise AgentValidationError(msg, cause=e) from e
    else:
        return data


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load and parse YAML file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
        return _parse_yaml_string(content, str(file_path))
    except OSError as e:
        msg = f"Failed to read file: {e}"
        raise AgentValidationError(msg, file_path, e) from e


def _load_agent_by_identifier(
    identifier: str,
    resolver: AgentResolver,
    current_file: Path | None,
    visited: set[Path | str],
    depth: int,
) -> YamlAgentDocument:
    """Load agent using resolver (supports names, paths, URLs).

    Args:
        identifier: Agent identifier (name, path, or URL)
        resolver: Agent resolver instance
        current_file: Current file path for relative resolution
        visited: Set of visited sources for cycle detection
        depth: Current recursion depth

    Returns:
        YamlAgentDocument with resolved references

    Raises:
        AgentValidationError: If loading or validation fails
        AgentCycleError: If circular references detected

    """
    # Resolve the identifier
    try:
        resolution = resolver.resolve(identifier, current_file)
    except ValueError as e:
        msg = f"Failed to resolve agent identifier '{identifier}': {e}"
        raise AgentValidationError(msg, current_file, e) from e

    # Check for cycles using source as key
    source_key = resolution.file_path if resolution.file_path else resolution.source
    if source_key in visited:
        cycle_path = " -> ".join(str(p) for p in visited) + f" -> {source_key}"
        msg = f"Circular reference detected: {cycle_path}"
        raise AgentCycleError(msg, current_file)

    # Parse YAML
    data = _parse_yaml_string(resolution.content, resolution.source)

    # Validate and parse with Pydantic
    try:
        spec = YamlAgentSpec.model_validate(data)
    except ValidationError as e:
        msg = f"Agent specification validation failed for {resolution.source}: {e}"
        raise AgentValidationError(msg, resolution.file_path, e) from e

    # Additional validation
    _validate_agent_spec(spec, resolution.file_path or Path(resolution.source), depth)

    # Resolve references
    visited_copy = visited.copy()
    visited_copy.add(source_key)
    resolved_spec = _resolve_agent_refs(
        spec,
        resolution.file_path or Path.cwd(),
        visited_copy,
        depth,
        resolver,
    )

    return YamlAgentDocument(spec=resolved_spec, file_path=resolution.file_path)


def _validate_agent_spec(
    spec: YamlAgentSpec,
    file_path: Path,
    depth: int,
) -> None:
    """Validate agent specification beyond Pydantic validation."""
    # Enforce global_instruction only at root level
    if depth > 0 and spec.global_instruction is not None:
        msg = "global_instruction can only be used at the root agent level"
        raise AgentValidationError(msg, file_path)


def _resolve_agent_refs(
    spec: YamlAgentSpec,
    current_file: Path,
    visited: set[Path | str],
    depth: int,
    resolver: AgentResolver,
) -> YamlAgentSpec:
    """Recursively resolve $ref references in agent specification.

    Args:
        spec: Agent specification to resolve
        current_file: Path of the current file being processed
        visited: Set of already visited sources for cycle detection
        depth: Current recursion depth
        resolver: Agent resolver for loading references

    Returns:
        Agent specification with all references resolved

    Raises:
        AgentCycleError: If circular references detected
        AgentValidationError: If reference resolution fails

    """
    if depth > MAX_REF_DEPTH:
        msg = f"Maximum reference depth ({MAX_REF_DEPTH}) exceeded"
        raise AgentValidationError(msg, current_file)

    # Resolve sub_agents
    resolved_sub_agents: list[AgentRef | InlineAgentSpec] = []
    for sub_agent in spec.sub_agents:
        if isinstance(sub_agent, AgentRef):
            # Use resolver to load by identifier (name, path, or URL)
            referenced_doc = _load_agent_by_identifier(
                sub_agent.ref,
                resolver,
                current_file,
                visited,
                depth + 1,
            )
            resolved_sub_agents.append(InlineAgentSpec(agent=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(sub_agent, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                sub_agent.agent,
                current_file,
                visited,
                depth + 1,
                resolver,
            )
            resolved_sub_agents.append(InlineAgentSpec(agent=resolved_inline))
        else:
            resolved_sub_agents.append(sub_agent)

    # Resolve agent_tools
    resolved_agent_tools: list[ToolSpec | AgentRef | InlineAgentSpec] = []
    for agent_tool in spec.tools:
        if isinstance(agent_tool, AgentRef):
            # Use resolver to load by identifier (name, path, or URL)
            referenced_doc = _load_agent_by_identifier(
                agent_tool.ref,
                resolver,
                current_file,
                visited,
                depth + 1,
            )
            resolved_agent_tools.append(InlineAgentSpec(agent=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(agent_tool, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                agent_tool.agent,
                current_file,
                visited,
                depth + 1,
                resolver,
            )
            resolved_agent_tools.append(InlineAgentSpec(agent=resolved_inline))
        else:
            resolved_agent_tools.append(agent_tool)

    # Create new spec with resolved references
    return YamlAgentSpec(
        version=spec.version,
        kind=spec.kind,
        name=spec.name,
        description=spec.description,
        model=spec.model,
        instruction=spec.instruction,
        global_instruction=spec.global_instruction,
        prompt=spec.prompt,
        attributes=spec.attributes,
        adk=spec.adk,
        tools=resolved_agent_tools,
        sub_agents=resolved_sub_agents,
    )


def _load_agent_yaml(
    file_path: Path,
    visited: set[Path | str] | None = None,
    depth: int = 0,
    resolver: AgentResolver | None = None,
) -> YamlAgentDocument:
    """Load an agent from a YAML file.

    Args:
        file_path: Path to the agent YAML file
        visited: Set of visited identifiers (paths, URLs, names) for cycle detection
        depth: Current recursion depth
        resolver: Agent resolver for $ref resolution

    Returns:
        YamlAgentDocument with resolved references

    Raises:
        AgentValidationError: If loading or validation fails

    """
    if visited is None:
        visited = set()

    if resolver is None:
        resolver = AgentResolver()

    file_path = file_path.resolve()

    if not file_path.exists():
        msg = f"Agent file not found: {file_path}"
        raise AgentValidationError(msg, file_path)

    # Load and parse YAML
    data = _load_yaml_file(file_path)

    # Validate and parse with Pydantic
    try:
        spec = YamlAgentSpec.model_validate(data)
    except ValidationError as e:
        msg = f"Agent specification validation failed for {file_path}: {e}"
        raise AgentValidationError(msg, file_path, e) from e

    # Additional validation
    _validate_agent_spec(spec, file_path, depth)

    # Resolve references
    visited.add(file_path)
    resolved_spec = _resolve_agent_refs(spec, file_path, visited, depth, resolver)

    return YamlAgentDocument(spec=resolved_spec, file_path=file_path)


class YamlAgentLoader(AgentLoader):
    """YAML agent loader implementing the AgentLoader interface."""

    def __init__(
        self,
        base_paths: list[Path | str] | list[Path] | list[str],
        http_auth: str | None = None,
    ) -> None:
        """Initialize the YAML agent loader.

        Args:
            base_paths: List of base paths to search for agents
            http_auth: Authorization header value for HTTP agent URIs

        """
        self.base_paths = [p if isinstance(p, Path) else Path(p) for p in base_paths]
        self.http_auth = http_auth
        self._discovered_agents: list[AgentInfo] | None = None

    def discover(self) -> list[AgentInfo]:
        """Discover YAML agents in the given paths.

        Returns:
            List of discovered YAML agents as AgentInfo objects

        """
        if self._discovered_agents is not None:
            return self._discovered_agents

        agents: list[AgentInfo] = []
        # Discover both .yaml and .yml files
        yaml_files = find_files(self.base_paths, "*.yaml")
        yml_files = find_files(self.base_paths, "*.yml")
        agent_files = yaml_files + yml_files

        # Create resolver for discovery (no auth needed for local files)
        resolver = AgentResolver(discovered_agents=[], http_auth=self.http_auth)

        for agent_file in agent_files:
            try:
                agent_doc = _load_agent_yaml(agent_file, resolver=resolver)
                # TODO(agents): Figure out a way to handle agents with the same name
                # There can be multiple agents with the same name, which creates an
                # inconsistent behavior.
                agent_info = AgentInfo(
                    name=agent_doc.get_name(),
                    description=agent_doc.get_description(),
                    file_path=agent_doc.file_path,
                    yaml_document=agent_doc,
                )
                agents.append(agent_info)
            except AgentValidationError as e:
                logger.warning("Doesn't look like agent: %s\n%s", agent_file, e)

        self._discovered_agents = agents
        return agents

    def load_agent(self, agent: "str | Path | AgentInfo") -> "StreetRaceAgent":
        """Load a YAML agent by name, path, or AgentInfo.

        Args:
            agent: Agent identifier (name, path, URL, or AgentInfo)

        Returns:
            Loaded StreetRaceAgent implementation

        Raises:
            ValueError: If agent cannot be loaded

        """
        from streetrace.agents.base_agent_loader import AgentInfo
        from streetrace.agents.yaml_agent import YamlAgent

        yaml_document: YamlAgentDocument

        if isinstance(agent, AgentInfo):
            if not agent.yaml_document:
                msg = f"AgentInfo does not contain YAML agent data: {agent.name}"
                raise ValueError(msg)
            return YamlAgent(agent.yaml_document)

        # Create resolver with discovered agents for name resolution
        discovered = self.discover()
        resolver = AgentResolver(discovered_agents=discovered, http_auth=self.http_auth)

        if isinstance(agent, str):
            # Try to resolve using resolver (handles names, paths, URLs)
            try:
                yaml_document = _load_agent_by_identifier(
                    agent,
                    resolver,
                    None,
                    set(),
                    0,
                )
                return YamlAgent(yaml_document)
            except AgentValidationError as e:
                msg = f"Failed to load YAML agent from '{agent}': {e}"
                raise ValueError(msg) from e

        if isinstance(agent, Path):
            try:
                yaml_document = _load_agent_yaml(agent, resolver=resolver)
            except AgentValidationError as e:
                msg = f"Failed to load YAML agent from {agent}: {e}"
                raise ValueError(msg) from e
            else:
                return YamlAgent(yaml_document)

        msg = f"Yaml agent not found: {agent}"
        raise ValueError(msg)
