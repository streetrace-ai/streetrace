"""YAML definition loader.

This module provides the YamlDefinitionLoader class for parsing YAML agent
content into YamlWorkloadDefinition instances.

After SourceResolver consolidation, this loader only handles parsing.
Discovery and resolution are handled by SourceResolver.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from streetrace.agents.base_agent_loader import AgentValidationError
from streetrace.agents.resolver import SourceResolution, SourceResolver, SourceType
from streetrace.agents.yaml_models import YamlAgentSpec
from streetrace.log import get_logger
from streetrace.workloads.metadata import WorkloadMetadata
from streetrace.workloads.yaml_definition import YamlWorkloadDefinition

logger = get_logger(__name__)


class YamlDefinitionLoader:
    """Loader for YAML agent content.

    Parses YAML during load() - no deferred parsing. This ensures that invalid
    content is rejected early during discovery rather than at execution time.

    This class implements the DefinitionLoader protocol. Discovery and
    resolution are handled by SourceResolver.
    """

    def __init__(self, http_auth: str | None = None) -> None:
        """Initialize the YAML definition loader.

        Args:
            http_auth: Optional authorization header value for resolving
                $ref references over HTTP

        """
        self._http_auth = http_auth

    def load(self, resolution: SourceResolution) -> YamlWorkloadDefinition:
        """Parse YAML content from a SourceResolution.

        Parsing happens immediately. Invalid content raises exceptions.
        This ensures that the returned YamlWorkloadDefinition always has
        a valid spec.

        Args:
            resolution: SourceResolution containing YAML content

        Returns:
            A fully populated YamlWorkloadDefinition with spec

        Raises:
            AgentValidationError: If parsing or validation fails

        """
        source = resolution.source
        content = resolution.content

        logger.debug("Parsing YAML from: %s", source)

        # Parse YAML
        try:
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                msg = f"YAML must contain a mapping/object, got {type(data).__name__}"
                raise AgentValidationError(msg, resolution.file_path)
        except yaml.YAMLError as e:
            msg = f"Invalid YAML syntax in {source}: {e}"
            raise AgentValidationError(msg, resolution.file_path, e) from e

        # Validate with Pydantic model
        try:
            spec = YamlAgentSpec.model_validate(data)
        except ValidationError as e:
            msg = f"Agent specification validation failed for {source}: {e}"
            raise AgentValidationError(msg, resolution.file_path, e) from e

        # Resolve $ref references if any
        resolved_spec = self._resolve_references(spec, resolution)

        # Create metadata from the spec
        metadata = WorkloadMetadata(
            name=resolved_spec.name,
            description=resolved_spec.description,
            source_path=resolution.file_path,
            format="yaml",
        )

        logger.debug("Loaded YAML definition '%s' from %s", metadata.name, source)

        return YamlWorkloadDefinition(
            metadata=metadata,
            spec=resolved_spec,
        )

    def _resolve_references(
        self,
        spec: YamlAgentSpec,
        resolution: SourceResolution,
    ) -> YamlAgentSpec:
        """Resolve $ref references in the YAML spec.

        Uses the existing reference resolution infrastructure from
        yaml_agent_loader.

        Args:
            spec: The parsed YAML agent spec
            resolution: Source resolution for context (path or URL)

        Returns:
            The spec with all references resolved

        """
        # Import the resolution function from yaml_agent_loader
        from streetrace.agents.yaml_agent_loader import _resolve_agent_refs

        # Create resolver for fetching referenced content
        resolver = SourceResolver(discovered_sources={}, http_auth=self._http_auth)

        # Determine base path and visited set based on source type
        if resolution.source_type == SourceType.HTTP_URL:
            # URL source: use cwd for relative resolution, track URL as visited
            visited: set[Path | str] = {resolution.source}
            base_path = Path.cwd()
        else:
            # File source: use file path for relative resolution
            base_path = resolution.file_path or Path.cwd()
            visited = {base_path}

        return _resolve_agent_refs(spec, base_path, visited, depth=0, resolver=resolver)
