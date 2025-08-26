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


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load and parse YAML file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            msg = f"YAML file must contain a mapping/object, got {type(data).__name__}"
            raise AgentValidationError(msg, file_path)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML syntax: {e}"
        raise AgentValidationError(msg, file_path, e) from e
    except OSError as e:
        msg = f"Failed to read file: {e}"
        raise AgentValidationError(msg, file_path, e) from e
    else:
        return data


def _resolve_ref_path(ref_path: str, current_file: Path) -> Path:
    """Resolve a $ref path relative to the current file."""
    ref_path = ref_path.strip()

    # Handle absolute paths
    if ref_path.startswith("/"):
        return Path(ref_path)

    # Handle home directory
    if ref_path.startswith("~/"):
        return Path(ref_path).expanduser().resolve()

    # Handle relative paths
    return (current_file.parent / ref_path).resolve()


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
    visited: set[Path],
    depth: int = 0,
) -> YamlAgentSpec:
    """Recursively resolve $ref references in agent specification.

    Args:
        spec: Agent specification to resolve
        current_file: Path of the current file being processed
        visited: Set of already visited files for cycle detection
        depth: Current recursion depth

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
            ref_path = _resolve_ref_path(sub_agent.ref, current_file)

            # Check for cycles
            if ref_path in visited:
                cycle_path = " -> ".join(str(p) for p in visited) + f" -> {ref_path}"
                msg = f"Circular reference detected: {cycle_path}"
                raise AgentCycleError(msg, current_file)

            # Load and resolve referenced agent
            visited_copy = visited.copy()
            visited_copy.add(ref_path)

            referenced_doc = _load_agent_yaml(ref_path, visited_copy, depth + 1)
            resolved_sub_agents.append(InlineAgentSpec(agent=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(sub_agent, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                sub_agent.agent,
                current_file,
                visited,
                depth + 1,
            )
            resolved_sub_agents.append(InlineAgentSpec(agent=resolved_inline))
        else:
            resolved_sub_agents.append(sub_agent)

    # Resolve agent_tools
    resolved_agent_tools: list[ToolSpec | AgentRef | InlineAgentSpec] = []
    for agent_tool in spec.tools:
        if isinstance(agent_tool, AgentRef):
            ref_path = _resolve_ref_path(agent_tool.ref, current_file)

            # Check for cycles
            if ref_path in visited:
                cycle_path = " -> ".join(str(p) for p in visited) + f" -> {ref_path}"
                msg = f"Circular reference detected: {cycle_path}"
                raise AgentCycleError(msg, current_file)

            # Load and resolve referenced agent
            visited_copy = visited.copy()
            visited_copy.add(ref_path)

            referenced_doc = _load_agent_yaml(ref_path, visited_copy, depth + 1)
            resolved_agent_tools.append(InlineAgentSpec(agent=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(agent_tool, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                agent_tool.agent,
                current_file,
                visited,
                depth + 1,
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
        adk=spec.adk,
        tools=resolved_agent_tools,
        sub_agents=resolved_sub_agents,
    )


def _load_agent_yaml(
    file_path: Path,
    visited: set[Path] | None = None,
    depth: int = 0,
) -> YamlAgentDocument:
    """Load an agent from a YAML file.

    Args:
        file_path: Path to the agent YAML file
        visited: Set of visited files for cycle detection
        depth: Current recursion depth

    Returns:
        YamlAgentDocument with resolved references

    Raises:
        AgentValidationError: If loading or validation fails

    """
    if visited is None:
        visited = set()

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
    resolved_spec = _resolve_agent_refs(spec, file_path, visited, depth)

    return YamlAgentDocument(spec=resolved_spec, file_path=file_path)


class YamlAgentLoader(AgentLoader):
    """YAML agent loader implementing the AgentLoader interface."""

    def __init__(self, base_paths: list[Path | str] | list[Path] | list[str]) -> None:
        """Initialize the YAML agent loader.

        Args:
            base_paths: List of base paths to search for agents

        """
        self.base_paths = [p if isinstance(p, Path) else Path(p) for p in base_paths]

    def discover(self) -> list[AgentInfo]:
        """Discover YAML agents in the given paths.

        Args:
            paths: List of paths to search for agents

        Returns:
            List of discovered YAML agents as AgentInfo objects

        """
        agents: list[AgentInfo] = []
        # Discover both .yaml and .yml files
        yaml_files = find_files(self.base_paths, "*.yaml")
        yml_files = find_files(self.base_paths, "*.yml")
        agent_files = yaml_files + yml_files

        for agent_file in agent_files:
            try:
                agent_doc = _load_agent_yaml(agent_file)
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
        return agents

    def load_agent(self, agent: "str | Path | AgentInfo") -> "StreetRaceAgent":
        """Load a YAML agent by name, path, or AgentInfo.

        Args:
            agent: Agent identifier

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

        if isinstance(agent, str):
            known_agent = next(
                (a for a in self.discover() if a.name.lower() == agent.lower()),
                None,
            )
            if known_agent:
                return self.load_agent(known_agent)

        if isinstance(agent, str) and Path(agent).is_file():
            return self.load_agent(Path(agent))

        if isinstance(agent, Path):
            try:
                yaml_document = _load_agent_yaml(agent)
            except AgentValidationError as e:
                msg = f"Failed to load YAML agent from {agent}: {e}"
                raise ValueError(msg) from e
            else:
                return YamlAgent(yaml_document)

        msg = f"Yaml agent not found: {agent}"
        raise ValueError(msg)
