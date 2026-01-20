"""DSL agent loader for .sr files.

Provide loading and discovery of Streetrace DSL agent files for integration
with the AgentManager.
"""

from pathlib import Path

from streetrace.dsl.cache import BytecodeCache
from streetrace.dsl.compiler import compile_dsl, get_bytecode_cache
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.log import get_logger

logger = get_logger(__name__)


def _to_class_name(filename: str) -> str:
    """Convert filename to valid Python class name.

    Args:
        filename: The filename (without extension).

    Returns:
        CamelCase class name ending with 'Workflow'.

    """
    # Remove file extension if present
    name = Path(filename).stem

    # Convert to CamelCase
    parts = name.replace("-", "_").split("_")
    camel_case = "".join(part.capitalize() for part in parts if part)

    return f"{camel_case}Workflow"


class DslAgentLoader:
    """Loader for .sr DSL agent files.

    Load and discover Streetrace DSL files, compiling them to executable
    workflow classes.
    """

    def __init__(self, cache: BytecodeCache | None = None) -> None:
        """Initialize the DSL agent loader.

        Args:
            cache: Optional bytecode cache. Uses global cache if not provided.

        """
        self._cache = cache or get_bytecode_cache()
        logger.debug("Created DslAgentLoader")

    def can_load(self, path: Path) -> bool:
        """Check if this loader can handle the given path.

        Args:
            path: Path to check.

        Returns:
            True if path has .sr extension.

        """
        return path.suffix == ".sr"

    def load(self, path: Path) -> type[DslAgentWorkflow]:
        """Load a DSL file and return a workflow class.

        Compile the DSL file to Python bytecode and run it to obtain
        the workflow class.

        Args:
            path: Path to the .sr file.

        Returns:
            Generated workflow class.

        Raises:
            FileNotFoundError: If the file does not exist.
            DslSyntaxError: If parsing fails.
            DslSemanticError: If semantic analysis fails.
            ValueError: If no workflow class is found in the compiled code.

        """
        if not path.exists():
            msg = f"DSL file not found: {path}"
            raise FileNotFoundError(msg)

        logger.debug("Loading DSL file: %s", path)
        source = path.read_text()

        # Compile the DSL source
        bytecode, source_map = compile_dsl(source, str(path))

        # Run bytecode to get the class
        namespace: dict[str, object] = {}
        # SECURITY: This is intentional for DSL loading.
        # The bytecode is generated from a validated DSL file.
        exec(bytecode, namespace)  # noqa: S102  # nosec B102

        # Find the generated workflow class
        for obj_name, obj in namespace.items():
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, DslAgentWorkflow):
                continue
            if obj_name == "DslAgentWorkflow":
                continue
            logger.debug(
                "Loaded workflow class %s from %s",
                obj_name,
                path,
            )
            # Type is verified by isinstance and issubclass checks above
            workflow_class: type[DslAgentWorkflow] = obj
            return workflow_class

        msg = f"No workflow class found in {path}"
        raise ValueError(msg)

    def discover(self, directory: Path) -> list[Path]:
        """Discover all .sr files in a directory.

        Recursively search for all .sr files in the given directory.

        Args:
            directory: Directory to search.

        Returns:
            List of paths to discovered .sr files.

        """
        if not directory.is_dir():
            logger.debug("Not a directory: %s", directory)
            return []

        discovered = list(directory.rglob("*.sr"))
        logger.debug("Discovered %d .sr files in %s", len(discovered), directory)
        return discovered
