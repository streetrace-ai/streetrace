"""Definition loader protocol.

This module provides the DefinitionLoader protocol that defines the interface
for loading workload definitions from various source formats.

After the SourceResolver consolidation, loaders are simplified:
- SourceResolver handles discovery and resolution (finding agents)
- Loaders only handle parsing (loading content into WorkloadDefinition)
"""

from typing import Protocol, runtime_checkable

from streetrace.agents.resolver import SourceResolution
from streetrace.workloads.definition import WorkloadDefinition


@runtime_checkable
class DefinitionLoader(Protocol):
    """Protocol for loading workload definitions from SourceResolution.

    A DefinitionLoader is responsible for parsing source content into
    WorkloadDefinition instances. Each loader handles a specific format
    (DSL, YAML, Python).

    The key contract is that load() must parse the content immediately.
    Invalid content should raise appropriate exceptions rather than
    returning incomplete definitions.

    Discovery and resolution are handled by SourceResolver, not loaders.
    """

    def load(self, resolution: SourceResolution) -> WorkloadDefinition:
        """Load and parse a workload definition from resolved source.

        This method must parse the content immediately. Invalid content
        should raise appropriate exceptions.

        Args:
            resolution: SourceResolution containing content and metadata.
                - DSL and YAML loaders use resolution.content
                - Python loader uses resolution.file_path (requires import)

        Returns:
            A fully populated WorkloadDefinition instance

        Raises:
            ValueError: If the content cannot be parsed or is invalid

        """
        ...
