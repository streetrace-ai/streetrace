"""DSL agent loader for .sr files.

Provide loading and discovery of Streetrace DSL agent files for integration
with the AgentManager through the AgentLoader interface.
"""

from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent

    from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider

from streetrace.agents.base_agent_loader import AgentInfo, AgentLoader
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping
from streetrace.log import get_logger

logger = get_logger(__name__)


class DslAgentInfo(AgentInfo):
    """Agent information container for DSL agents."""

    def __init__(
        self,
        name: str,
        description: str,
        file_path: Path,
        workflow_class: type[DslAgentWorkflow] | None = None,
    ) -> None:
        """Initialize DSL agent info.

        Args:
            name: Agent name.
            description: Agent description.
            file_path: Path to the .sr file.
            workflow_class: Compiled workflow class (optional).

        """
        super().__init__(name=name, description=description, file_path=file_path)
        self.workflow_class = workflow_class

    @property
    def kind(self) -> str:  # type: ignore[override]
        """Get the definition type of the agent."""
        return "dsl"


class DslAgentLoader(AgentLoader):
    """Agent loader for .sr DSL files.

    Discover and load Streetrace DSL files, compiling them to executable
    workflow classes that can be used as agents.
    """

    def __init__(self) -> None:
        """Initialize the DSL agent loader."""
        logger.debug("Created DslAgentLoader")

    def discover_in_paths(self, paths: list[Path]) -> list[AgentInfo]:
        """Discover .sr agents in specific paths.

        Args:
            paths: Specific paths to search in.

        Returns:
            List of discovered DSL agents.

        """
        discovered: list[AgentInfo] = []

        for search_path in paths:
            if not search_path.exists():
                continue

            # Find all .sr files
            if search_path.is_file() and search_path.suffix == ".sr":
                sr_files = [search_path]
            elif search_path.is_dir():
                sr_files = list(search_path.glob("*.sr"))
            else:
                continue

            for sr_file in sr_files:
                try:
                    agent_info = self._extract_agent_info(sr_file)
                    discovered.append(agent_info)
                    logger.debug(
                        "Discovered DSL agent '%s' at %s",
                        agent_info.name,
                        sr_file,
                    )
                except (ValueError, OSError) as e:
                    logger.debug(
                        "Failed to extract agent info from %s: %s",
                        sr_file,
                        e,
                    )

        return discovered

    def _extract_agent_info(self, file_path: Path) -> DslAgentInfo:
        """Extract agent information from a .sr file.

        Args:
            file_path: Path to the .sr file.

        Returns:
            DslAgentInfo with basic metadata.

        """
        # Use filename (without extension) as agent name
        name = file_path.stem

        # Try to extract description from file header comments
        description = f"DSL agent from {file_path.name}"
        try:
            source = file_path.read_text()
            # Look for description in first comment block
            for raw_line in source.split("\n")[:10]:
                stripped = raw_line.strip()
                if stripped.startswith("#"):
                    # Use first comment line as description
                    description = stripped.lstrip("# ").strip()
                    break
        except OSError:
            pass

        return DslAgentInfo(
            name=name,
            description=description,
            file_path=file_path,
        )

    def load_from_path(self, path: Path) -> StreetRaceAgent:
        """Load agent from explicit file path.

        Args:
            path: Path to .sr file.

        Returns:
            Loaded DSL agent.

        Raises:
            ValueError: If cannot load from this path.

        """
        if not path.exists():
            msg = f"DSL file not found: {path}"
            raise ValueError(msg)

        if path.is_dir():
            # Look for .sr files in directory
            sr_files = list(path.glob("*.sr"))
            if not sr_files:
                msg = f"No .sr files found in directory: {path}"
                raise ValueError(msg)
            path = sr_files[0]

        if path.suffix != ".sr":
            msg = f"Not a DSL file (.sr): {path}"
            raise ValueError(msg)

        return self._load_dsl_file(path)

    def load_from_url(self, url: str) -> StreetRaceAgent:
        """Load agent from HTTP URL.

        DSL files from URLs are not currently supported.

        Args:
            url: HTTP(S) URL.

        Raises:
            ValueError: Always, as URL loading is not supported.

        """
        msg = f"Loading DSL agents from URLs is not supported: {url}"
        raise ValueError(msg)

    def load_agent(self, agent_info: AgentInfo) -> StreetRaceAgent:
        """Load agent from AgentInfo (from discovery).

        Args:
            agent_info: Previously discovered agent info.

        Returns:
            Loaded DSL agent.

        Raises:
            ValueError: If cannot load this agent.

        """
        if not agent_info.file_path:
            msg = f"AgentInfo for '{agent_info.name}' has no file path"
            raise ValueError(msg)

        return self._load_dsl_file(agent_info.file_path)

    def _load_dsl_file(self, path: Path) -> StreetRaceAgent:
        """Load and compile a DSL file.

        Args:
            path: Path to the .sr file.

        Returns:
            DslStreetRaceAgent wrapping the compiled workflow.

        Raises:
            ValueError: If compilation fails.

        """
        from streetrace.dsl import DslSemanticError, DslSyntaxError, compile_dsl

        logger.debug("Loading DSL agent from %s", path)

        try:
            source = path.read_text()
        except OSError as e:
            msg = f"Failed to read DSL file {path}: {e}"
            raise ValueError(msg) from e

        try:
            bytecode, source_map = compile_dsl(source, str(path))
        except DslSyntaxError as e:
            msg = f"Syntax error in {path}: {e}"
            raise ValueError(msg) from e
        except DslSemanticError as e:
            msg = f"Semantic error in {path}: {e}"
            raise ValueError(msg) from e

        # Execute bytecode to get workflow class
        namespace: dict[str, object] = {}
        # SECURITY NOTE: exec is used intentionally here to load validated DSL bytecode.
        # The bytecode is generated from a DSL file that has passed semantic analysis.
        # This is similar to how Python's importlib loads compiled .pyc files.
        compiled_exec(bytecode, namespace)

        # Find the generated workflow class
        workflow_class: type[DslAgentWorkflow] | None = None
        for obj_name, obj in namespace.items():
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, DslAgentWorkflow):
                continue
            if obj_name == "DslAgentWorkflow":
                continue
            workflow_class = obj
            break

        if workflow_class is None:
            msg = f"No workflow class found in compiled DSL: {path}"
            raise ValueError(msg)

        logger.debug("Loaded workflow class %s from %s", workflow_class.__name__, path)

        # Create and return the StreetRaceAgent wrapper
        return DslStreetRaceAgent(
            workflow_class=workflow_class,
            source_file=path,
            source_map=source_map,
        )


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


class DslStreetRaceAgent(StreetRaceAgent):
    """StreetRaceAgent wrapper for compiled DSL workflows.

    Wrap a compiled DSL workflow class to implement the StreetRaceAgent
    interface required by the AgentManager.
    """

    def __init__(
        self,
        workflow_class: type[DslAgentWorkflow],
        source_file: Path,
        source_map: list[SourceMapping],
    ) -> None:
        """Initialize the DSL agent wrapper.

        Args:
            workflow_class: Compiled workflow class.
            source_file: Path to the source .sr file.
            source_map: Source mappings for error translation.

        """
        self._workflow_class = workflow_class
        self._source_file = source_file
        self._source_map = source_map
        self._workflow_instance: DslAgentWorkflow | None = None

    def get_agent_card(self) -> "StreetRaceAgentCard":
        """Provide an A2A AgentCard."""
        from a2a.types import AgentCapabilities, AgentSkill

        from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

        name = self._source_file.stem
        skill = AgentSkill(
            id=f"dsl_{name}",
            name=name,
            description=f"DSL agent from {self._source_file.name}",
            tags=["dsl"],
            examples=[f"Use the {name} DSL agent"],
        )
        return StreetRaceAgentCard(
            name=name,
            description=f"DSL agent from {self._source_file.name}",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
        )

    async def create_agent(
        self,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",  # noqa: ARG002
        system_context: "SystemContext",  # noqa: ARG002
    ) -> "BaseAgent":
        """Create the ADK agent from the DSL workflow.

        Args:
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.

        Returns:
            The root ADK agent.

        """
        from google.adk.agents import LlmAgent

        # Create workflow instance
        self._workflow_instance = self._workflow_class()

        # Get model from workflow's _models dict
        model_name = None
        if hasattr(self._workflow_class, "_models"):
            models = self._workflow_class._models  # noqa: SLF001
            if models:
                # Use 'main' model if available, otherwise first model
                model_name = models.get("main") or next(iter(models.values()), None)

        # Get model - use specified model from DSL or fall back to current model
        if model_name:
            model = model_factory.get_llm_interface(model_name).get_adk_llm()
        else:
            model = model_factory.get_current_model()

        # Get instruction from workflow's _prompts dict
        instruction = "You are a helpful assistant."
        if hasattr(self._workflow_class, "_prompts"):
            prompts = self._workflow_class._prompts  # noqa: SLF001
            # Look for instruction prompt
            for key, prompt_value in prompts.items():
                if "instruction" in key.lower() or "greeting" in key.lower():
                    # Prompts can be strings or lambda functions
                    if callable(prompt_value):
                        try:
                            from streetrace.dsl.runtime.context import WorkflowContext

                            ctx = WorkflowContext()
                            instruction = str(prompt_value(ctx))
                        except (TypeError, KeyError):
                            # Fallback: convert to string
                            instruction = str(prompt_value)
                    else:
                        instruction = str(prompt_value)
                    break

        # Note: Tool loading from DSL is not yet fully implemented
        # Tools defined in DSL need to be mapped to ToolRef objects

        return LlmAgent(
            name=self._source_file.stem,
            model=model,
            instruction=instruction,
        )

    async def close(self, agent_instance: "BaseAgent") -> None:  # noqa: ARG002
        """Clean up resources."""
        self._workflow_instance = None

    def get_attributes(self) -> dict[str, Any]:
        """Get custom attributes for this agent."""
        return {
            "streetrace.agent.type": "dsl",
            "streetrace.agent.source": str(self._source_file),
        }

    def get_version(self) -> str | None:
        """Get the version of this agent."""
        return None

    def get_system_prompt(self) -> str | None:
        """Get the system prompt for this agent."""
        if hasattr(self._workflow_class, "_prompts"):
            prompts = self._workflow_class._prompts  # noqa: SLF001
            for key in prompts:
                if "instruction" in key.lower():
                    return f"<prompt: {key}>"
        return None

    @property
    def user_prompt(self) -> str | None:
        """Get the user prompt for this agent."""
        return None
