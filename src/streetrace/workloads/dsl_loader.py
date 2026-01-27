"""DSL definition loader.

This module provides the DslDefinitionLoader class for compiling DSL source
content into DslWorkloadDefinition instances.

After SourceResolver consolidation, this loader only handles parsing.
Discovery and resolution are handled by SourceResolver.
"""

from pathlib import Path
from types import CodeType

from streetrace.agents.resolver import SourceResolution
from streetrace.dsl.compiler import DslSemanticError, DslSyntaxError, compile_dsl
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.log import get_logger
from streetrace.workloads.dsl_definition import DslWorkloadDefinition
from streetrace.workloads.metadata import WorkloadMetadata

logger = get_logger(__name__)


class DslDefinitionLoader:
    """Loader for DSL source content.

    Compiles DSL source during load() - no deferred compilation. This ensures
    that invalid content is rejected early during discovery rather than at
    execution time.

    This class implements the DefinitionLoader protocol. Discovery and
    resolution are handled by SourceResolver.
    """

    def load(self, resolution: SourceResolution) -> DslWorkloadDefinition:
        """Compile DSL content from a SourceResolution.

        Compilation happens immediately. Invalid content raises exceptions.
        This ensures that the returned DslWorkloadDefinition always has
        a valid workflow_class.

        Args:
            resolution: SourceResolution containing DSL source content

        Returns:
            A fully populated DslWorkloadDefinition with workflow_class

        Raises:
            DslSyntaxError: If parsing fails
            DslSemanticError: If semantic analysis fails
            ValueError: If no workflow class is found in compiled code

        """
        source = resolution.content
        source_path = resolution.file_path or Path(resolution.source)

        logger.debug("Compiling DSL from: %s", resolution.source)

        # Compile the DSL source
        try:
            bytecode, source_map = compile_dsl(source, str(source_path))
        except DslSyntaxError:
            logger.debug("Syntax error in %s", resolution.source)
            raise
        except DslSemanticError:
            logger.debug("Semantic error in %s", resolution.source)
            raise

        # Run bytecode to get workflow class
        # SECURITY NOTE: compiled_exec is used for validated DSL bytecode loading.
        # The bytecode is generated from a DSL file that has passed semantic analysis.
        # Include __name__ so Pydantic create_model() can determine module context.
        namespace: dict[str, object] = {"__name__": f"dsl.{source_path.stem}"}
        compiled_exec(bytecode, namespace)

        # Find the workflow class in the namespace
        workflow_class = self._find_workflow_class(namespace, source_path)

        # Extract metadata from the compiled class and source
        metadata = WorkloadMetadata(
            name=self._extract_name(source_path),
            description=self._extract_description(source_path, source),
            source_path=resolution.file_path,
            format="dsl",
        )

        logger.debug(
            "Loaded DSL definition '%s' from %s with workflow class %s",
            metadata.name,
            resolution.source,
            workflow_class.__name__,
        )

        return DslWorkloadDefinition(
            metadata=metadata,
            workflow_class=workflow_class,
            source_map=source_map,
        )

    def _find_workflow_class(
        self,
        namespace: dict[str, object],
        source_path: Path,
    ) -> type[DslAgentWorkflow]:
        """Find the workflow class in the compiled namespace.

        Search the namespace for a class that:
        1. Is a type (not an instance)
        2. Is a subclass of DslAgentWorkflow
        3. Is not DslAgentWorkflow itself (must be generated class)

        Args:
            namespace: The namespace from executed bytecode
            source_path: Path to the source file (for error messages)

        Returns:
            The workflow class found in the namespace

        Raises:
            ValueError: If no workflow class is found

        """
        for obj_name, obj in namespace.items():
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, DslAgentWorkflow):
                continue
            if obj_name == "DslAgentWorkflow":
                continue

            # Fool-proof: Ensure generated class doesn't override __init__
            # This would break the constructor-based dependency injection contract
            if "__init__" in obj.__dict__:
                msg = (
                    f"Generated workflow class '{obj_name}' in {source_path} "
                    "must not override __init__. This is a compiler bug."
                )
                raise ValueError(msg)

            # Found the generated workflow class
            return obj

        msg = f"No workflow class found in compiled DSL: {source_path}"
        raise ValueError(msg)

    def _extract_name(self, path: Path) -> str:
        """Extract the workload name from the filename.

        Args:
            path: Path to the source file

        Returns:
            The workload name (filename without extension)

        """
        return path.stem

    def _extract_description(self, path: Path, source: str) -> str:
        """Extract the workload description from source comments.

        Looks for the first comment line in the source file. If none found,
        returns a default description with the filename.

        Args:
            path: Path to the source file
            source: The original source code

        Returns:
            The workload description

        """
        # Try to extract from first comment line
        for raw_line in source.split("\n")[:10]:
            stripped = raw_line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("# ").strip()

        # Default description
        return f"DSL workload from {path.name}"


def compiled_exec(bytecode: CodeType, namespace: dict[str, object]) -> None:
    """Execute compiled bytecode in a namespace.

    This function wraps exec for executing validated DSL bytecode.
    The bytecode has been generated from a DSL source that passed
    semantic validation.

    Args:
        bytecode: Compiled Python bytecode.
        namespace: Namespace to execute in.

    """
    # SECURITY: exec is intentional here for validated DSL bytecode loading.
    exec(bytecode, namespace)  # noqa: S102  # nosec B102
