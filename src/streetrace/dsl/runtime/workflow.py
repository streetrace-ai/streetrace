"""Base workflow class for Streetrace DSL.

Provide the base class that all generated workflows extend.
This class implements the Workload protocol for unified execution.
"""

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from streetrace.dsl.runtime.context import WorkflowContext, deep_parse_json_strings
from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.events import HistoryCompactionEvent
from streetrace.dsl.runtime.history_compactor import (
    HistoryCompactor,
    extract_messages_from_events,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content
    from pydantic import BaseModel

    from streetrace.dsl.runtime.events import FlowEvent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory

logger = get_logger(__name__)

MAX_AGENT_SCHEMA_RETRIES = 1
"""Maximum retry attempts for agent schema validation (1 retry = 2 total attempts)."""


def _try_parse_json(value: object) -> object:
    """Try to parse a string value as JSON.

    Agent results are often JSON-formatted text. Parse them into
    native Python objects (lists, dicts) so flow code can operate
    on structured data. Return the original value if parsing fails.

    Args:
        value: Value to try parsing.

    Returns:
        Parsed JSON object, or original value if not JSON.

    """
    if not isinstance(value, str):
        return value
    import json

    # Strip markdown code fences if present (opening + content + closing)
    min_fenced_lines = 3
    text = value.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) >= min_fenced_lines and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return value


@dataclass
class EscalationSpec:
    """Escalation specification for prompt outputs.

    Define the condition under which a prompt's output triggers escalation.
    Used with PromptSpec to specify when an agent should escalate.
    """

    op: str
    """Comparison operator: '~', '==', '!=', 'contains'."""

    value: str
    """Value to compare against."""


@dataclass
class PromptSpec:
    """Prompt specification with optional schema and escalation.

    Wrap a prompt body lambda with optional model, schema, and escalation
    configuration. This allows prompts to define expected output structure
    and when their output should trigger escalation.
    """

    body: Callable[[object], str]
    """Lambda that takes context and returns the prompt text."""

    model: str | None = None
    """Optional model name for this prompt."""

    schema: str | None = None
    """Optional schema name for structured output validation."""

    escalation: EscalationSpec | None = None
    """Optional escalation condition."""


@dataclass
class EntryPoint:
    """Represent an entry point for workflow execution."""

    type: str
    """Entry point type: 'flow' or 'agent'."""

    name: str


@dataclass
class SchemaValidationParams:
    """Parameters for agent result schema validation.

    Bundle validation parameters to reduce argument count in methods.
    """

    schema_name: str | None
    """Full schema name (e.g., 'Finding[]')."""

    schema_model: "type[BaseModel]"
    """Pydantic model class for validation."""

    is_array: bool
    """True if expecting an array of schema items."""
    """Name of the flow or agent."""


class DslAgentWorkflow:
    """Base class for generated DSL workflows.

    Generated workflows extend this class and override
    the class attributes and event handler methods.

    This class implements the Workload protocol for unified execution
    and uses composition to delegate agent creation to DslAgentFactory.

    All runtime dependencies are provided via constructor. Generated subclasses
    must NOT override __init__ - they only define class attributes and methods.
    """

    _models: ClassVar[dict[str, str]] = {}
    """Model definitions for this workflow."""

    _schemas: ClassVar[dict[str, "type[BaseModel]"]] = {}
    """Schema definitions for this workflow as Pydantic models."""

    _prompts: ClassVar[dict[str, object]] = {}
    """Prompt definitions for this workflow."""

    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    """Tool definitions for this workflow."""

    _agents: ClassVar[dict[str, dict[str, object]]] = {}
    """Agent definitions for this workflow."""

    _compaction_policy: ClassVar[dict[str, object] | None] = None
    """Default compaction policy for history management."""

    def __init__(
        self,
        *,
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
        agent_factory: "DslAgentFactory | None" = None,
    ) -> None:
        """Initialize the workflow with all required dependencies.

        Args:
            model_factory: Factory for creating LLM models.
            tool_provider: Provider for tools.
            system_context: System context.
            session_service: Session service for Runner.
            agent_factory: DslAgentFactory for agent creation.

        """
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._agent_factory = agent_factory
        self._context: WorkflowContext | None = None
        self._created_agents: list[BaseAgent] = []

        logger.debug("Created %s", self.__class__.__name__)

    def _determine_entry_point(self) -> EntryPoint:
        """Determine the entry point for workflow execution.

        Priority:
        1. 'main' flow if defined
        2. 'default' flow if defined
        3. 'default' agent if defined

        Returns:
            EntryPoint with type and name.

        Raises:
            ValueError: If no entry point found.

        """
        # Check for main flow
        flow_main = getattr(self, "flow_main", None)
        if flow_main is not None and callable(flow_main):
            return EntryPoint(type="flow", name="main")

        # Check for default flow
        flow_default = getattr(self, "flow_default", None)
        if flow_default is not None and callable(flow_default):
            return EntryPoint(type="flow", name="default")

        # Check for main agent
        if "main" in self._agents:
            return EntryPoint(type="agent", name="main")

        # Check for default agent
        if "default" in self._agents:
            return EntryPoint(type="agent", name="default")

        # Check for default agent
        if len(self._agents) == 1:
            agent_name = next(iter(self._agents.keys()))
            return EntryPoint(type="agent", name=agent_name)

        # If main/default flow and default agent not found, we can't run
        # anything as it introduces ambiguity.

        msg = "No entry point found in workflow"
        raise ValueError(msg)

    async def _create_agent(self, agent_name: str) -> "BaseAgent":
        """Create fully-configured ADK agent from DSL definition.

        Delegate to DslAgentFactory for agent creation.

        Args:
            agent_name: Name of the agent to create.

        Returns:
            Created ADK BaseAgent.

        Raises:
            ValueError: If agent_factory is not set.

        """
        if not self._agent_factory:
            msg = "DslAgentWorkflow requires agent_factory"
            raise ValueError(msg)

        agent = await self._agent_factory.create_agent(
            agent_name=agent_name,
            model_factory=self._model_factory,
            tool_provider=self._tool_provider,
            system_context=self._system_context,
        )
        self._created_agents.append(agent)
        return agent

    async def _execute_agent(
        self,
        agent_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute an agent and yield events.

        Args:
            agent_name: Name of the agent to execute.
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            ADK events from execution.

        """
        from google.adk import Runner

        agent = await self._create_agent(agent_name)

        # Use the provided session service
        if not self._session_service:
            msg = "Session service not available for agent execution"
            raise ValueError(msg)

        runner = Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=agent,
        )

        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            yield event

    def _extract_message_text(self, message: "Content | None") -> str:
        """Extract text content from a message.

        Args:
            message: User message content, or None.

        Returns:
            The text content of the message, or empty string if None.

        """
        if message is None:
            return ""
        if message.parts:
            # Concatenate text from all parts
            texts = [
                part.text
                for part in message.parts
                if hasattr(part, "text") and part.text
            ]
            return " ".join(texts)
        return ""

    def _resolve_agent_schema(
        self,
        agent_name: str,
    ) -> tuple[str | None, "type[BaseModel] | None", bool]:
        """Resolve the expected schema from an agent's instruction prompt.

        Look up the agent's instruction prompt and extract its schema definition.
        Return schema metadata for validation.

        Args:
            agent_name: Name of the agent to resolve schema for.

        Returns:
            Tuple of (schema_name, schema_model, is_array).
            Returns (None, None, False) if no schema is defined.

        """
        agent_def = self._agents.get(agent_name)
        if not agent_def:
            return (None, None, False)

        instruction_name = agent_def.get("instruction")
        if not instruction_name or not isinstance(instruction_name, str):
            return (None, None, False)

        prompt_spec = self._prompts.get(instruction_name)
        if not prompt_spec:
            return (None, None, False)

        schema_name = getattr(prompt_spec, "schema", None)
        if not schema_name or not isinstance(schema_name, str):
            return (None, None, False)

        # Check if array type
        is_array = schema_name.endswith("[]")
        base_name = schema_name[:-2] if is_array else schema_name

        schema_model = self._schemas.get(base_name)
        if not schema_model:
            return (None, None, False)

        return (schema_name, schema_model, is_array)

    def _validate_agent_result(
        self,
        raw_response: str,
        schema_model: "type[BaseModel]",
        *,
        is_array: bool,
    ) -> object:
        """Validate an agent's raw response against a schema.

        Parse the response as JSON and validate against the Pydantic model.

        Args:
            raw_response: The raw text response from the agent.
            schema_model: Pydantic model class for validation.
            is_array: True if expecting an array of schema items.

        Returns:
            Validated result as dict or list of dicts.

        Raises:
            JSONParseError: If response cannot be parsed as JSON.
            SchemaValidationError: If parsed response fails validation.

        """
        from pydantic import ValidationError as PydanticValidationError

        if not self._context:
            msg = "Context required for validation"
            raise ValueError(msg)

        # Parse JSON using context's method (let JSONParseError propagate)
        parsed = self._context._parse_json_response(raw_response)  # noqa: SLF001

        # Pre-process to handle JSON strings in nested fields
        # Type is preserved (dict stays dict, list stays list)
        parsed = deep_parse_json_strings(parsed)  # type: ignore[assignment]

        # Validate against schema
        try:
            if is_array:
                if not isinstance(parsed, list):
                    msg = f"Expected JSON array, got {type(parsed).__name__}"
                    raise JSONParseError(
                        raw_response=raw_response,
                        parse_error=msg,
                    )
                validated_items = []
                for item in parsed:
                    validated = schema_model.model_validate(item)
                    validated_items.append(validated.model_dump())
                return validated_items
            validated = schema_model.model_validate(parsed)
            return validated.model_dump()
        except PydanticValidationError as e:
            raise SchemaValidationError(
                schema_name=schema_model.__name__,
                errors=[str(e)],
                raw_response=raw_response,
            ) from e

    async def _execute_flow(
        self,
        flow_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute a flow, yielding events.

        Args:
            flow_name: Name of the flow to execute.
            session: ADK session (reserved for future event forwarding).
            message: User message to process.

        Yields:
            Events from all operations within the flow.

        """
        # Reserved for future event forwarding (Option 2/3 in design doc)
        _ = session

        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        # Extract user input and create context with built-in variables
        input_text = self._extract_message_text(message)
        ctx = self.create_context(input_prompt=input_text)

        # Flow method is now a generator - iterate and yield events
        async for event in flow_method(ctx):
            yield event

        # Yield flow result if return statement was executed
        if "_return_value" in ctx.vars:
            from streetrace.dsl.runtime.events import FlowResultEvent

            yield FlowResultEvent(result=ctx.vars["_return_value"])

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute the workload based on DSL definition.

        Entry point selection:
        1. If DSL defines a 'main' flow -> run_flow('main')
        2. Else if DSL defines a 'default' agent -> run_agent('default')
        3. Else run first defined agent

        Args:
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            Events from execution (ADK events or FlowEvents).

        """
        entry_point = self._determine_entry_point()

        if entry_point.type == "flow":
            async for event in self._execute_flow(entry_point.name, session, message):
                yield event
        else:
            async for event in self._execute_agent(entry_point.name, session, message):
                yield event

    async def run_agent(
        self,
        agent_name: str,
        *args: object,
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Run an agent from within a flow, yielding events.

        Called by generated flow code via ctx.run_agent().
        Uses _create_agent() which delegates to DslAgentFactory.

        When the agent's prompt has an `expecting` schema, the result is
        validated against that schema. On validation failure, the agent
        is retried once with error feedback. If retry also fails, an
        empty result ([] for arrays, {} for objects) is stored.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.

        Yields:
            ADK events from agent execution.

        Raises:
            ValueError: If agent_factory not set.

        """
        # Resolve schema for validation
        schema_name, schema_model, is_array = self._resolve_agent_schema(agent_name)

        # Execute agent and collect response
        final_response, events = await self._execute_agent_run(agent_name, *args)

        # Yield all collected events
        for event in events:
            yield event

        # Validate and potentially retry
        if self._context:
            if schema_model is None:
                # No schema - use simple JSON parsing
                self._context._last_call_result = _try_parse_json(  # noqa: SLF001
                    final_response,
                )
            else:
                # Schema validation with retry
                params = SchemaValidationParams(
                    schema_name=schema_name,
                    schema_model=schema_model,
                    is_array=is_array,
                )
                result = await self._validate_with_retry(
                    agent_name=agent_name,
                    raw_response=str(final_response) if final_response else "",
                    params=params,
                    args=args,
                )
                self._context._last_call_result = result  # noqa: SLF001

        # Check and perform history compaction if configured
        history_strategy = self._get_agent_history_strategy(agent_name)
        if history_strategy:
            async for compaction_event in self._check_and_compact_history(
                agent_name, events, history_strategy,
            ):
                yield compaction_event

    async def _execute_agent_run(
        self,
        agent_name: str,
        *args: object,
    ) -> tuple[object, list["Event"]]:
        """Execute a single agent run and collect events.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.

        Returns:
            Tuple of (final_response, collected_events).

        """
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        agent = await self._create_agent(agent_name)

        # Build prompt from args
        prompt_text = "\n---\n".join(str(arg) for arg in args) if args else ""
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)

        # Use InMemorySessionService for nested runs (isolated context)
        nested_session_service = InMemorySessionService()  # type: ignore[no-untyped-call]

        await nested_session_service.create_session(
            app_name="dsl_workflow",
            user_id="workflow_user",
            session_id="nested_session",
            state={},
        )

        runner = Runner(
            app_name="dsl_workflow",
            session_service=nested_session_service,
            agent=agent,
        )

        final_response: object = None
        collected_events: list[Event] = []

        async for event in runner.run_async(
            user_id="workflow_user",
            session_id="nested_session",
            new_message=content,
        ):
            collected_events.append(event)
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text

        return final_response, collected_events

    async def _validate_with_retry(
        self,
        agent_name: str,
        raw_response: str,
        params: SchemaValidationParams,
        args: tuple[object, ...],
    ) -> object:
        """Validate agent result with one retry on failure.

        Args:
            agent_name: Name of the agent (for retry).
            raw_response: The raw response text to validate.
            params: Schema validation parameters.
            args: Original args for retry.

        Returns:
            Validated result, or empty fallback on failure.

        """
        # First attempt
        first_error = ""
        try:
            return self._validate_agent_result(
                raw_response, params.schema_model, is_array=params.is_array,
            )
        except (JSONParseError, SchemaValidationError) as e:
            first_error = str(e)
            logger.debug(
                "Agent '%s' validation failed, retrying: %s",
                agent_name,
                first_error,
            )

        # Retry with error feedback appended to args
        error_feedback = (
            f"Error: Your response could not be parsed. {first_error}\n\n"
            f"Please respond with valid JSON matching the expected schema."
        )
        retry_args = (*args, error_feedback)

        retry_response, _ = await self._execute_agent_run(agent_name, *retry_args)

        # Second attempt
        try:
            return self._validate_agent_result(
                str(retry_response) if retry_response else "",
                params.schema_model,
                is_array=params.is_array,
            )
        except (JSONParseError, SchemaValidationError):
            logger.warning(
                "Agent '%s' expected %s but returned unparseable response after retry",
                agent_name,
                params.schema_name,
            )
            # Fall back to empty result
            return [] if params.is_array else {}

    async def run_flow(
        self,
        flow_name: str,
        *args: object,
        caller_ctx: "WorkflowContext | None" = None,
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Run a flow from within another flow, yielding events.

        Sub-flows share the caller's variable scope so they can access
        and modify variables set by the parent flow.

        Args:
            flow_name: Name of the flow to run.
            *args: Arguments to pass to the flow.
            caller_ctx: Parent context to share. Creates a new one if None.

        Yields:
            Events from flow execution.

        Raises:
            ValueError: If flow not found.

        """
        _ = args  # Available for future use
        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        ctx = caller_ctx if caller_ctx is not None else self.create_context()
        async for event in flow_method(ctx):
            yield event

    async def _execute_parallel_agents(
        self,
        ctx: WorkflowContext,
        specs: list[tuple[str, list[object], str | None]],
    ) -> AsyncGenerator["Event", None]:
        """Execute multiple agents in parallel using ADK ParallelAgent.

        Create sub-agents with output_key for result storage in session state,
        wrap them in a ParallelAgent, and execute using Runner. Events are
        yielded as they occur, and results are stored directly in ctx.vars.

        The order of events and results from parallel execution is non-deterministic.

        Args:
            ctx: Workflow context for variable access and result storage.
            specs: List of (agent_name, args, target_var) tuples. The target_var
                may be None if no result assignment is needed.

        Yields:
            ADK events from parallel agent execution.

        """
        from google.adk import Runner
        from google.adk.agents import ParallelAgent
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        if not specs:
            return

        if not self._agent_factory:
            msg = "DslAgentWorkflow requires agent_factory for parallel execution"
            raise ValueError(msg)

        # Create sub-agents with output_keys for result storage
        sub_agents = []
        output_key_mapping: dict[str, str] = {}  # target_var -> output_key

        for agent_name, _, target_var in specs:
            # Generate unique output_key for session state storage
            output_key = f"_parallel_{agent_name}_{id(specs)}"
            if target_var is not None:
                output_key_mapping[target_var] = output_key

            agent = await self._agent_factory.create_agent(
                agent_name=agent_name,
                model_factory=self._model_factory,
                tool_provider=self._tool_provider,
                system_context=self._system_context,
                output_key=output_key,
            )
            sub_agents.append(agent)

        # Create ParallelAgent to orchestrate concurrent execution
        parallel_agent = ParallelAgent(
            name=f"parallel_block_{id(specs)}",
            sub_agents=sub_agents,
        )

        # Build input message from first agent's args
        # All parallel agents receive the same initial context
        first_args = specs[0][1] if specs else []
        prompt_text = " ".join(str(arg) for arg in first_args) if first_args else ""
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)

        # Use InMemorySessionService for parallel execution (isolated context)
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        app_name = "dsl_parallel"
        user_id = "workflow_user"
        session_id = f"parallel_session_{id(specs)}"

        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={},
        )

        runner = Runner(
            app_name=app_name,
            session_service=session_service,
            agent=parallel_agent,
        )

        # Execute ParallelAgent and yield events as they occur
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            yield event

        # Get session and extract results from state
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        # Store results directly in ctx.vars with schema validation
        logger.debug(
            "Parallel execution complete. Session state keys: %s, "
            "output_key_mapping: %s",
            list(session.state.keys()) if session and session.state else "None",
            output_key_mapping,
        )

        # Build mapping from target_var to (agent_name, args) for retries
        target_var_to_spec: dict[str, tuple[str, list[object]]] = {}
        for agent_name, args, target_var in specs:
            if target_var is not None:
                target_var_to_spec[target_var] = (agent_name, args)

        if session and session.state:
            await self._process_parallel_results(
                ctx, session.state, output_key_mapping, target_var_to_spec,
            )

    async def _process_parallel_results(
        self,
        ctx: WorkflowContext,
        state: dict[str, object],
        output_key_mapping: dict[str, str],
        target_var_to_spec: dict[str, tuple[str, list[object]]],
    ) -> None:
        """Process and validate parallel agent results.

        Extract results from session state, validate against schemas,
        and store in context variables.

        Args:
            ctx: Workflow context for variable storage.
            state: Session state containing agent outputs.
            output_key_mapping: Maps target_var to output_key in state.
            target_var_to_spec: Maps target_var to (agent_name, args).

        """
        for target_var, output_key in output_key_mapping.items():
            if output_key not in state:
                continue

            raw = state[output_key]
            agent_name, args = target_var_to_spec.get(target_var, (target_var, []))

            # Resolve schema for this agent
            schema_name, schema_model, is_array = self._resolve_agent_schema(agent_name)

            if schema_model is None:
                # No schema - use simple JSON parsing
                parsed = _try_parse_json(raw)
                logger.debug(
                    "Parallel result for %s: type=%s (no schema)",
                    target_var,
                    type(parsed).__name__,
                )
                ctx.vars[target_var] = parsed
            else:
                # Validate with retry
                params = SchemaValidationParams(
                    schema_name=schema_name,
                    schema_model=schema_model,
                    is_array=is_array,
                )
                result = await self._validate_parallel_result(
                    agent_name=agent_name,
                    raw_response=str(raw) if raw else "",
                    params=params,
                    args=tuple(args),
                )
                logger.debug(
                    "Parallel result for %s: type=%s (validated)",
                    target_var,
                    type(result).__name__,
                )
                ctx.vars[target_var] = result

    async def _validate_parallel_result(
        self,
        agent_name: str,
        raw_response: str,
        params: SchemaValidationParams,
        args: tuple[object, ...],
    ) -> object:
        """Validate parallel agent result with one sequential retry on failure.

        Similar to _validate_with_retry but uses sequential execution for retry
        since parallel execution already completed.

        Args:
            agent_name: Name of the agent (for retry).
            raw_response: The raw response text to validate.
            params: Schema validation parameters.
            args: Original args for retry.

        Returns:
            Validated result, or empty fallback on failure.

        """
        # First attempt
        first_error = ""
        try:
            return self._validate_agent_result(
                raw_response, params.schema_model, is_array=params.is_array,
            )
        except (JSONParseError, SchemaValidationError) as e:
            first_error = str(e)
            logger.debug(
                "Parallel agent '%s' validation failed, retrying sequentially: %s",
                agent_name,
                first_error,
            )

        # Sequential retry with error feedback
        error_feedback = (
            f"Error: Your response could not be parsed. {first_error}\n\n"
            f"Please respond with valid JSON matching the expected schema."
        )
        retry_args = (*args, error_feedback)

        retry_response, _ = await self._execute_agent_run(agent_name, *retry_args)

        # Second attempt
        try:
            return self._validate_agent_result(
                str(retry_response) if retry_response else "",
                params.schema_model,
                is_array=params.is_array,
            )
        except (JSONParseError, SchemaValidationError):
            logger.warning(
                "Parallel agent '%s' expected %s but returned unparseable "
                "response after retry",
                agent_name,
                params.schema_name,
            )
            # Fall back to empty result
            return [] if params.is_array else {}

    def _get_agent_history_strategy(self, agent_name: str) -> str | None:
        """Get the history management strategy for an agent.

        Priority:
        1. Agent's explicit history property
        2. Compaction policy's strategy (workflow default)

        Args:
            agent_name: Name of the agent.

        Returns:
            Strategy name ('summarize' or 'truncate') or None if not configured.

        """
        agent_def = self._agents.get(agent_name)

        # First check agent's explicit history property
        if agent_def:
            history = agent_def.get("history")
            if history:
                return str(history)

        # Fall back to compaction policy if defined
        if self._compaction_policy:
            strategy = self._compaction_policy.get("strategy")
            if strategy:
                return str(strategy)

        return None

    def _get_agent_model(self, agent_name: str) -> str:
        """Resolve the model name for an agent.

        Look up the agent's model from its definition or use default.

        Args:
            agent_name: Name of the agent.

        Returns:
            Model identifier string.

        """
        # Check if agent has a specific model configured
        agent_def = self._agents.get(agent_name)
        if agent_def:
            # Check for model in agent definition
            model_name = agent_def.get("model")
            if model_name and isinstance(model_name, str):
                # Resolve model reference
                if model_name in self._models:
                    return self._models[model_name]
                return model_name

        # Use first model defined or default
        if self._models:
            return next(iter(self._models.values()))

        return "gpt-4"  # Default fallback

    def _get_model_max_input_tokens(self, agent_name: str) -> int | None:
        """Get max_input_tokens setting for an agent's model.

        Args:
            agent_name: Name of the agent.

        Returns:
            Max input tokens or None to use LiteLLM lookup.

        """
        # Look for max_input_tokens in model properties
        agent_def = self._agents.get(agent_name)
        if not agent_def:
            return None

        model_name = agent_def.get("model")
        if not model_name or not isinstance(model_name, str):
            # Use first model
            model_name = next(iter(self._models.keys()), None) if self._models else None

        if not model_name:
            return None

        # Get model properties (stored in class during codegen)
        # For now, max_input_tokens from DSL is stored in model properties
        # This requires the model definition to include max_input_tokens
        return None  # Will be enhanced when model properties are fully exposed

    async def _check_and_compact_history(
        self,
        agent_name: str,
        events: list["Event"],
        strategy: str,
    ) -> AsyncGenerator["HistoryCompactionEvent", None]:
        """Check if history needs compaction and perform it if needed.

        Args:
            agent_name: Name of the agent for model lookup.
            events: Collected events from agent execution.
            strategy: Compaction strategy name.

        Yields:
            HistoryCompactionEvent if compaction was performed.

        """
        model = self._get_agent_model(agent_name)
        max_input_tokens = self._get_model_max_input_tokens(agent_name)

        # Extract messages from events
        messages = extract_messages_from_events(events)

        if not messages:
            return

        # Create compactor with strategy
        compactor = HistoryCompactor(
            strategy=strategy,
            llm_client=None,  # LLM client for summarize strategy (future enhancement)
        )

        # Check if compaction is needed
        if not compactor.should_compact(messages, model, max_input_tokens):
            return

        # Perform compaction
        result = await compactor.compact(messages, model, max_input_tokens)

        logger.info(
            "Compacted history for agent '%s': %d -> %d tokens, %d messages removed",
            agent_name,
            result.original_tokens,
            result.compacted_tokens,
            result.messages_removed,
        )

        # Yield compaction event for visibility
        yield HistoryCompactionEvent(
            strategy=strategy,
            original_tokens=result.original_tokens,
            compacted_tokens=result.compacted_tokens,
            messages_removed=result.messages_removed,
        )

    async def close(self) -> None:
        """Clean up all created agents.

        This method is called when the workload context manager exits.
        It closes all agents that were created during execution.
        """
        for agent in self._created_agents:
            if self._agent_factory:
                await self._agent_factory.close(agent)
        self._created_agents.clear()

    def create_context(
        self,
        *,
        input_prompt: str = "",
    ) -> WorkflowContext:
        """Create a new workflow context.

        Args:
            input_prompt: The user's input prompt (built-in variable).

        Returns:
            A fresh WorkflowContext connected to this workflow.

        """
        ctx = WorkflowContext(workflow=self)
        ctx.set_models(self._models)
        ctx.set_prompts(self._prompts)
        ctx.set_agents(self._agents)
        ctx.set_schemas(self._schemas)

        # Set built-in variables
        ctx.vars["input_prompt"] = input_prompt

        self._context = ctx
        return ctx

    async def on_start(self, ctx: WorkflowContext) -> None:
        """Handle workflow start event.

        Override this method to initialize global variables.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_input(self, ctx: WorkflowContext) -> None:
        """Handle input event.

        Override this method to process/guard input.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_output(self, ctx: WorkflowContext) -> None:
        """Handle output event.

        Override this method to process/guard output.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle tool call event.

        Override this method to intercept tool calls.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle tool result event.

        Override this method to process tool results.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_start(self, ctx: WorkflowContext) -> None:
        """Handle after start event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_input(self, ctx: WorkflowContext) -> None:
        """Handle after input event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_output(self, ctx: WorkflowContext) -> None:
        """Handle after output event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle after tool call event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle after tool result event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use
