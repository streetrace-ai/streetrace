"""YAML agent loader with validation and reference resolution."""

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from streetrace.agents.yaml_models import (
    AgentDocument,
    AgentRef,
    InlineAgentSpec,
    YamlAgentSpec,
)
from streetrace.log import get_logger

logger = get_logger(__name__)

# Maximum depth for $ref resolution to prevent infinite recursion
MAX_REF_DEPTH = 5

# Default search paths for agent autodiscovery
DEFAULT_AGENT_PATHS = [
    "./agents",
    ".",  # for *.agent.y{a,}ml files
    "~/.streetrace/agents",
    "/etc/streetrace/agents",  # Unix only
]


class AgentValidationError(Exception):
    """Raised when agent validation fails."""

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.file_path = file_path
        self.cause = cause
        super().__init__(message)


class AgentCycleError(AgentValidationError):
    """Raised when circular references are detected."""


class AgentDuplicateNameError(AgentValidationError):
    """Raised when duplicate agent names are found."""


def _expand_path(path_str: str) -> Path:
    """Expand user home directory and resolve path."""
    return Path(path_str).expanduser().resolve()


def _get_agent_search_paths() -> list[Path]:
    """Get list of paths to search for agents."""
    paths = []

    # Add default paths
    for path_str in DEFAULT_AGENT_PATHS:
        try:
            path = _expand_path(path_str)
            if path.exists() and path.is_dir():
                paths.append(path)
        except (OSError, ValueError):
            # Skip invalid paths
            continue

    # Add paths from environment variable
    env_paths = os.environ.get("STREETRACE_AGENT_PATHS", "")
    if env_paths:
        for path_str in env_paths.split(":"):
            if not path_str.strip():
                continue
            try:
                path = _expand_path(path_str.strip())
                if path.exists() and path.is_dir():
                    paths.append(path)
            except (OSError, ValueError):
                logger.warning("Invalid path in STREETRACE_AGENT_PATHS: %s", path_str)
                continue

    return paths


def _discover_agent_files() -> list[Path]:
    """Discover all agent YAML files in search paths."""
    agent_files = []

    for search_path in _get_agent_search_paths():
        if not search_path.exists():
            continue

        # Pattern 1: ./agents/*.y{a,}ml - Only in directories named "agents"
        if search_path.name == "agents" or search_path.parts[-1] == "agents":
            for pattern in ["*.yml", "*.yaml"]:
                agent_files.extend(search_path.glob(pattern))
        else:
            # For non-agents directories, look for any .yml/.yaml files as
            # potential agents
            # This allows tests and other scenarios to work
            for pattern in ["*.yml", "*.yaml"]:
                agent_files.extend(search_path.glob(pattern))

        # Pattern 2: ./*.agent.y{a,}ml - Always check for this pattern
        for pattern in ["*.agent.yml", "*.agent.yaml"]:
            agent_files.extend(search_path.glob(pattern))

    # Remove duplicates and sort
    return sorted(set(agent_files))


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
        return _expand_path(ref_path)

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
    resolved_sub_agents = []
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

            referenced_doc = load_agent_from_file(ref_path, visited_copy, depth + 1)
            resolved_sub_agents.append(InlineAgentSpec(inline=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(sub_agent, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                sub_agent.inline,
                current_file,
                visited,
                depth + 1,
            )
            resolved_sub_agents.append(InlineAgentSpec(inline=resolved_inline))
        else:
            resolved_sub_agents.append(sub_agent)

    # Resolve agent_tools
    resolved_agent_tools = []
    for agent_tool in spec.agent_tools:
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

            referenced_doc = load_agent_from_file(ref_path, visited_copy, depth + 1)
            resolved_agent_tools.append(InlineAgentSpec(inline=referenced_doc.spec))
        # Inline agent - resolve its references recursively
        elif isinstance(agent_tool, InlineAgentSpec):
            resolved_inline = _resolve_agent_refs(
                agent_tool.inline,
                current_file,
                visited,
                depth + 1,
            )
            resolved_agent_tools.append(InlineAgentSpec(inline=resolved_inline))
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
        tools=spec.tools,
        sub_agents=resolved_sub_agents,
        agent_tools=resolved_agent_tools,
    )


def load_agent_from_file(
    file_path: Path,
    visited: set[Path] | None = None,
    depth: int = 0,
) -> AgentDocument:
    """Load an agent from a YAML file.

    Args:
        file_path: Path to the agent YAML file
        visited: Set of visited files for cycle detection
        depth: Current recursion depth

    Returns:
        AgentDocument with resolved references

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
        msg = f"Agent specification validation failed: {e}"
        raise AgentValidationError(msg, file_path, e) from e

    # Additional validation
    _validate_agent_spec(spec, file_path, depth)

    # Resolve references
    visited.add(file_path)
    resolved_spec = _resolve_agent_refs(spec, file_path, visited, depth)

    return AgentDocument(spec=resolved_spec, file_path=file_path)


def discover_agents() -> list[AgentDocument]:
    """Discover all agents in search paths.

    Returns:
        List of discovered agent documents

    Raises:
        AgentDuplicateNameError: If duplicate agent names found

    """
    agent_files = _discover_agent_files()
    agents = []
    name_to_files: dict[str, list[Path]] = defaultdict(list)

    for file_path in agent_files:
        try:
            agent_doc = load_agent_from_file(file_path)
            agents.append(agent_doc)
            name_to_files[agent_doc.get_name()].append(file_path)
        except AgentValidationError as e:
            logger.warning(
                "Failed to load agent from %s: %s",
                file_path,
                e,
                extra={"file_path": str(file_path), "error": str(e)},
            )
            continue

    # Check for duplicate names
    duplicates = {
        name: paths for name, paths in name_to_files.items() if len(paths) > 1
    }
    if duplicates:
        duplicate_info = []
        for name, paths in duplicates.items():
            path_list = ", ".join(str(p) for p in paths)
            duplicate_info.append(f"'{name}': [{path_list}]")

        msg = f"Duplicate agent names found: {'; '.join(duplicate_info)}"
        raise AgentDuplicateNameError(msg)

    return agents


def find_agent_by_name(name: str) -> AgentDocument | None:
    """Find an agent by name through autodiscovery.

    Args:
        name: Agent name to search for

    Returns:
        AgentDocument if found, None otherwise

    """
    try:
        agents = discover_agents()
        return next((agent for agent in agents if agent.get_name() == name), None)
    except (AgentValidationError, AgentDuplicateNameError):
        logger.exception("Failed to discover agents while searching for '%s'", name)
        return None


def validate_agent_file(file_path: Path) -> None:
    """Validate an agent file and all its references.

    Args:
        file_path: Path to agent file to validate

    Raises:
        AgentValidationError: If validation fails

    """
    load_agent_from_file(file_path)
