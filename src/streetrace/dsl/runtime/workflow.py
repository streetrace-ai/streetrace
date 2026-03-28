"""Base workflow class for Streetrace DSL.

Provide the base class that all generated workflows extend.
This class implements the Workload protocol for unified execution.
"""

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from streetrace.dsl.runtime.compacting_runner import CompactionStrategy
from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.schema_validator import (
    SchemaInfo,
    resolve_agent_schema,
    validate_response,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.plugins import BasePlugin
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content
    from pydantic import BaseModel

    from streetrace.dsl.runtime.events import FlowEvent, HistoryCompactionEvent
    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider
    from streetrace.workloads.agent_executor import CompactionParams
    from streetrace.workloads.dsl_agent_factory import DslAgentFactory

logger = get_logger(__name__)

MAX_AGENT_SCHEMA_RETRIES = 1
"""Maximum retry attempts for agent schema validation (1 retry = 2 total attempts)."""

SUMMARIZE_PROMPT = """\
Summarize this conversation concisely while preserving key information:

{text}

Provide a brief summary that captures the main points and context."""


class SummarizeLlmAdapter:
    """Adapter to use model factory for summarization.

    Wrap the workflow's model factory to implement the SummarizeLlm protocol
    required by SummarizeCompactionStrategy.
    """

    def __init__(self, model_factory: "ModelFactory", model: str) -> None:
        """Initialize the adapter.

        Args:
            model_factory: Factory for creating LLM interfaces.
            model: Model identifier to use for summarization.

        """
        self._model_factory = model_factory
        self._model = model

    async def summarize(self, text: str) -> str:
        """Summarize the given text using the LLM.

        Args:
            text: The text to summarize.

        Returns:
            The summary.

        """
        llm_interface = self._model_factory.get_llm_interface(self._model)

        messages = [
            {"role": "user", "content": SUMMARIZE_PROMPT.format(text=text)},
        ]

        try:
            response = await llm_interface.generate_async(messages, tools=[])
            # Extract content from response
            if response.get("choices"):
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return str(choice["message"]["content"])
            return text[:500] + "..."  # Fallback to truncation
        except Exception:  # noqa: BLE001
            logger.warning("Failed to generate summary, falling back to truncation")
            return text[:500] + "..."


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
        from streetrace.dsl.runtime.compaction_orchestrator import (
            CompactionOrchestrator,
        )
        from streetrace.dsl.runtime.session_deriver import SessionDeriver
        from streetrace.workloads.agent_executor import (
            AgentExecutor,
            CompactionParams,
        )

        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._agent_factory = agent_factory

        plugins = self._build_plugins()
        self._executor = AgentExecutor(
            session_service=session_service,
            plugins=plugins,
        )
        self._plugins = plugins
        self._compaction_params_cls = CompactionParams
        self._session_deriver = SessionDeriver(session_service=session_service)
        self._compaction = CompactionOrchestrator(
            models=self._models,
            agents=self._agents,
            compaction_policy=self._compaction_policy,
            model_factory=model_factory,
        )
        self._context: WorkflowContext | None = None
        self._created_agents: list[BaseAgent] = []

        logger.debug("Created %s", self.__class__.__name__)

    def _build_plugins(self) -> "list[BasePlugin]":
        """Build the list of ADK plugins for this workflow.

        Create a GuardrailPlugin only if the generated subclass
        overrides at least one event handler.

        Returns:
            List of BasePlugin instances (may be empty).

        """
        from streetrace.dsl.runtime.guardrail_plugin import GuardrailPlugin

        plugin = GuardrailPlugin(workflow=self)
        if plugin.has_any_handler():
            logger.debug("GuardrailPlugin activated for %s", self.__class__.__name__)
            return [plugin]
        return []

    def _derive_session_identifiers(
        self,
        agent_name: str,
        *,
        parallel_index: int | None = None,
    ) -> tuple[str, str, str]:
        """Derive session identifiers for a nested agent run.

        Delegate to SessionDeriver.

        Args:
            agent_name: Name of the agent being executed.
            parallel_index: Index for parallel execution uniqueness.

        Returns:
            Tuple of (app_name, user_id, session_id).

        """
        # Compute fallback app name from agent factory or class name
        if self._agent_factory and hasattr(self._agent_factory, "_source_file"):
            source_file = self._agent_factory._source_file  # noqa: SLF001
            fallback = source_file.stem if source_file else self.__class__.__name__
        else:
            fallback = self.__class__.__name__

        return self._session_deriver.derive_identifiers(
            agent_name,
            self._context,
            fallback,
            parallel_index=parallel_index,
        )

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

    def _create_compaction_strategy(self, agent_name: str) -> CompactionStrategy | None:
        """Create a compaction strategy for the agent if configured.

        Delegate to CompactionOrchestrator.

        Args:
            agent_name: Name of the agent.

        Returns:
            CompactionStrategy instance, or None if compaction not configured.

        """
        return self._compaction.create_strategy(agent_name)

    def _build_compaction_params(
        self,
        agent_name: str,
    ) -> "CompactionParams | None":
        """Build compaction params for an agent, or None if not configured."""
        strategy = self._create_compaction_strategy(agent_name)
        if strategy is None:
            return None
        return self._compaction_params_cls(
            strategy=strategy,
            max_tokens=self._compaction.get_model_max_input_tokens(agent_name),
            model=self._compaction.get_agent_model(agent_name),
        )

    async def _execute_agent(
        self,
        agent_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute an agent and yield events.

        Delegate to AgentExecutor which handles Runner creation, optional
        compaction, and async generator lifecycle.

        Args:
            agent_name: Name of the agent to execute.
            session: ADK session for conversation persistence.
            message: User message to process.

        Yields:
            ADK events from execution.

        """
        agent = await self._create_agent(agent_name)

        compaction = self._build_compaction_params(agent_name)

        async for event in self._executor.run(
            agent=agent,
            session=session,
            message=message,
            compaction=compaction,
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
            logger.debug("_extract_message_text: message is None")
            return ""
        if not message.parts:
            logger.debug("_extract_message_text: message.parts is empty/None")
            return ""
        # Concatenate text from all parts
        texts = []
        for part in message.parts:
            # Check for text attribute - google.genai.types.Part stores text directly
            if hasattr(part, "text") and part.text:
                texts.append(part.text)
                logger.debug(
                    "_extract_message_text: found text part (len=%d)",
                    len(part.text),
                )
        result = " ".join(texts)
        if not result:
            logger.warning(
                "_extract_message_text: no text extracted from %d parts",
                len(message.parts),
            )
        return result

    def _resolve_agent_schema(self, agent_name: str) -> SchemaInfo | None:
        """Resolve the expected schema from an agent's instruction prompt.

        Delegate to schema_validator module.

        Args:
            agent_name: Name of the agent to resolve schema for.

        Returns:
            SchemaInfo if schema is defined, None otherwise.

        """
        return resolve_agent_schema(
            agent_name, self._agents, self._prompts, self._schemas,
        )

    async def _execute_flow(
        self,
        flow_name: str,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event | FlowEvent", None]:
        """Execute a flow, yielding events.

        Args:
            flow_name: Name of the flow to execute.
            session: ADK session for session context propagation.
            message: User message to process.

        Yields:
            Events from all operations within the flow.

        """
        flow_method = getattr(self, f"flow_{flow_name}", None)
        if flow_method is None:
            msg = f"Flow '{flow_name}' not found"
            raise ValueError(msg)

        # Extract user input and create context with built-in variables
        input_text = self._extract_message_text(message)
        logger.debug(
            "_execute_flow(%s): input_text=%r (len=%d), message=%s",
            flow_name,
            input_text[:100] if input_text else "",
            len(input_text),
            "present" if message else "None",
        )
        ctx = self.create_context(input_prompt=input_text)

        # Propagate session context for nested agent execution
        ctx.set_parent_session(session)
        ctx.set_current_flow(flow_name)

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
        history: list[dict[str, object]] | None = None,
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
            history: Optional conversation history to seed the session.

        Yields:
            ADK events from agent execution.

        Raises:
            ValueError: If agent_factory not set.

        """
        # Resolve schema for validation
        schema_info = self._resolve_agent_schema(agent_name)

        # Execute agent and collect response
        final_response, events = await self._execute_agent_run(
            agent_name, *args, history=history,
        )

        # Yield all collected events
        for event in events:
            yield event

        # Validate and potentially retry
        if self._context:
            if schema_info is None:
                # No schema - use simple JSON parsing
                self._context._last_call_result = _try_parse_json(  # noqa: SLF001
                    final_response,
                )
            else:
                # Schema validation with retry
                result = await self._validate_with_retry(
                    agent_name=agent_name,
                    raw_response=str(final_response) if final_response else "",
                    schema_info=schema_info,
                    args=args,
                    history=history,
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
        history: list[dict[str, object]] | None = None,
    ) -> tuple[object, list["Event"]]:
        """Execute an agent from a flow, collecting events and final response.

        Build a child session and message content from args, then delegate
        to AgentExecutor for actual execution.

        Args:
            agent_name: Name of the agent to run.
            *args: Arguments to pass to the agent.
            history: Optional conversation history to seed the session.

        Returns:
            Tuple of (final_response, collected_events).

        """
        from google.adk.events import Event as AdkEvent
        from google.genai import types as genai_types

        agent = await self._create_agent(agent_name)

        # Build prompt from args
        prompt_text = "\n---\n".join(str(arg) for arg in args) if args else ""
        logger.debug(
            "_execute_agent_run(%s): args=%r, prompt_text=%r (len=%d)",
            agent_name,
            args,
            prompt_text[:100] if prompt_text else "",
            len(prompt_text),
        )
        content = None
        if prompt_text:
            parts = [genai_types.Part.from_text(text=prompt_text)]
            content = genai_types.Content(role="user", parts=parts)
        else:
            logger.warning(
                "_execute_agent_run(%s): prompt_text is empty, content will be None",
                agent_name,
            )

        # Derive session identifiers and get-or-create child session
        app_name, user_id, session_id = self._derive_session_identifiers(agent_name)
        existing = await self._session_deriver.get_or_create(
            app_name, user_id, session_id,
        )

        # Seed session with history if provided
        if history:
            adk_events = []
            for msg in history:
                if not isinstance(msg, dict):
                    # Fallback for unexpected string items in history
                    text = str(msg)
                    role = "user"
                else:
                    role = str(msg.get("role", "user"))
                    text = str(msg.get("content", ""))

                # ADK roles are "user" or agent name
                author = "user" if role == "user" else agent_name
                adk_event = AdkEvent(
                    author=author,
                    content=genai_types.Content(
                        role="user" if role == "user" else "model",
                        parts=[genai_types.Part.from_text(text=text)],
                    ),
                )
                adk_events.append(adk_event)

            # Replace events in the session with provided history
            # This effectively "seeds" the conversation
            await self._session_service.replace_events(  # type: ignore[attr-defined]
                session=existing,
                new_events=adk_events,
            )

        # Resolve compaction parameters
        compaction = self._build_compaction_params(agent_name)

        # Execute via AgentExecutor and collect events + final response
        final_response: object = None
        collected_events: list[Event] = []

        async for event in self._executor.run(
            agent=agent,
            session=existing,
            message=content,
            compaction=compaction,
        ):
            collected_events.append(event)
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text

        return final_response, collected_events

    async def _validate_with_retry(
        self,
        agent_name: str,
        raw_response: str,
        schema_info: SchemaInfo,
        args: tuple[object, ...],
        history: list[dict[str, object]] | None = None,
    ) -> object:
        """Validate agent result with one retry on failure.

        Args:
            agent_name: Name of the agent (for retry).
            raw_response: The raw response text to validate.
            schema_info: Resolved schema information.
            args: Original args for retry.
            history: Optional conversation history to seed the session.

        Returns:
            Validated result, or empty fallback on failure.

        """
        # First attempt
        first_error = ""
        try:
            return validate_response(
                raw_response,
                schema_info.schema_model,
                is_array=schema_info.is_array,
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

        retry_response, _ = await self._execute_agent_run(
            agent_name, *retry_args, history=history,
        )

        # Second attempt
        try:
            return validate_response(
                str(retry_response) if retry_response else "",
                schema_info.schema_model,
                is_array=schema_info.is_array,
            )
        except (JSONParseError, SchemaValidationError):
            logger.warning(
                "Agent '%s' expected %s but returned unparseable response after retry",
                agent_name,
                schema_info.schema_name,
            )
            # Fall back to empty result
            return [] if schema_info.is_array else {}

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
        wrap them in a ParallelAgent, and execute via AgentExecutor. Events are
        yielded as they occur, and results are stored directly in ctx.vars.

        The order of events and results from parallel execution is non-deterministic.

        Args:
            ctx: Workflow context for variable access and result storage.
            specs: List of (agent_name, args, target_var) tuples. The target_var
                may be None if no result assignment is needed.

        Yields:
            ADK events from parallel agent execution.

        """
        from google.adk.agents import ParallelAgent
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

        # Derive session identifiers and get-or-create for parallel block
        app_name, user_id, base_session_id = self._derive_session_identifiers(
            "parallel_block",
            parallel_index=0,
        )
        session_id = f"{base_session_id}_{id(specs)}"
        existing = await self._session_deriver.get_or_create(
            app_name, user_id, session_id,
        )

        # Execute ParallelAgent via AgentExecutor
        async for event in self._executor.run(
            agent=parallel_agent,
            session=existing,
            message=content,
        ):
            yield event

        # Get session and extract results from state
        session = await self._session_service.get_session(
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
            schema_info = self._resolve_agent_schema(agent_name)

            if schema_info is None:
                # No schema - use simple JSON parsing
                parsed = _try_parse_json(raw)
                logger.debug(
                    "Parallel result for %s: type=%s (no schema)",
                    target_var,
                    type(parsed).__name__,
                )
                ctx.vars[target_var] = parsed
            else:
                # Validate with retry (reuse same method as sequential)
                result = await self._validate_with_retry(
                    agent_name=agent_name,
                    raw_response=str(raw) if raw else "",
                    schema_info=schema_info,
                    args=tuple(args),
                )
                logger.debug(
                    "Parallel result for %s: type=%s (validated)",
                    target_var,
                    type(result).__name__,
                )
                ctx.vars[target_var] = result

    def _get_agent_history_strategy(self, agent_name: str) -> str | None:
        """Get the history management strategy for an agent.

        Delegate to CompactionOrchestrator.

        Args:
            agent_name: Name of the agent.

        Returns:
            Strategy name or None if not configured.

        """
        return self._compaction.get_history_strategy(agent_name)

    async def _check_and_compact_history(
        self,
        agent_name: str,
        events: list["Event"],
        strategy: str,
    ) -> AsyncGenerator["HistoryCompactionEvent", None]:
        """Check if history needs compaction and perform it if needed.

        Delegate to CompactionOrchestrator.

        Args:
            agent_name: Name of the agent for model lookup.
            events: Collected events from agent execution.
            strategy: Compaction strategy name.

        Yields:
            HistoryCompactionEvent if compaction was performed.

        """
        async for event in self._compaction.check_and_compact_history(
            agent_name, events, strategy,
        ):
            yield event

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
