# Workload Extension Guide

This guide explains how to create custom Workload implementations for StreetRace. Custom
workloads enable you to integrate new execution models, agent frameworks, or workflow systems.

## Overview

The Workload Protocol provides an abstraction for executable units in StreetRace. By implementing
this protocol, you can create workloads that:

- Execute custom agent types
- Integrate external agent frameworks
- Implement specialized execution patterns
- Add new workflow orchestration logic

## Implementing the Workload Protocol

### Basic Structure

A workload must implement two methods:

```python
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.genai.types import Content


class MyWorkload:
    """Custom workload implementation."""

    def run_async(
        self,
        session: Session,
        message: Content | None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the workload and yield events."""
        ...

    async def close(self) -> None:
        """Clean up all resources allocated by this workload."""
        ...
```

### Complete Example

Here is a complete example of a custom workload that wraps an external agent system:

```python
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from google.adk import Runner
from google.adk.agents import LlmAgent

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.genai.types import Content

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider

logger = get_logger(__name__)


class ExternalAgentWorkload:
    """Workload that wraps an external agent system."""

    def __init__(
        self,
        agent_config: dict[str, object],
        model_factory: "ModelFactory",
        tool_provider: "ToolProvider",
        system_context: "SystemContext",
        session_service: "BaseSessionService",
    ) -> None:
        """Initialize the external agent workload.

        Args:
            agent_config: Configuration for the external agent
            model_factory: Factory for creating LLM models
            tool_provider: Provider of tools for the agent
            system_context: System context with project instructions
            session_service: Session service for conversation persistence

        """
        self._config = agent_config
        self._model_factory = model_factory
        self._tool_provider = tool_provider
        self._system_context = system_context
        self._session_service = session_service
        self._agent: BaseAgent | None = None

    async def run_async(
        self,
        session: "Session",
        message: "Content | None",
    ) -> AsyncGenerator["Event", None]:
        """Execute the external agent and yield events.

        Args:
            session: ADK session for conversation persistence
            message: User message to process

        Yields:
            ADK events from execution

        """
        # Create the agent if not already created
        if self._agent is None:
            self._agent = await self._create_agent()

        # Create Runner with the session service
        runner = Runner(
            app_name=session.app_name,
            session_service=self._session_service,
            agent=self._agent,
        )

        # Run and yield all events
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            yield event

    async def _create_agent(self) -> "BaseAgent":
        """Create the ADK agent from external configuration.

        Returns:
            Configured BaseAgent instance

        """
        # Example: Create an LlmAgent from config
        model_id = self._config.get("model", "anthropic/claude-sonnet")
        instruction = self._config.get("instruction", "You are a helpful assistant.")

        # Resolve model through ModelFactory
        model = self._model_factory.get_model(model_id)

        # Get tools from ToolProvider
        tool_names = self._config.get("tools", [])
        tools = []
        for tool_name in tool_names:
            tool = await self._tool_provider.get_tool(tool_name)
            if tool:
                tools.append(tool)

        return LlmAgent(
            name=self._config.get("name", "external_agent"),
            model=model.model_id,
            instruction=instruction,
            tools=tools,
        )

    async def close(self) -> None:
        """Clean up the agent resources."""
        if self._agent:
            logger.debug("Closing external agent")
            # Perform any necessary cleanup
            self._agent = None
```

## Registering Custom Workloads

To use custom workloads with the WorkloadManager, you have two options:

### Option 1: Create a Custom DefinitionLoader

Create a definition loader that implements the `DefinitionLoader` protocol:

```python
from pathlib import Path

from streetrace.workloads import (
    DefinitionLoader,
    WorkloadDefinition,
    WorkloadMetadata,
)


class ExternalWorkloadDefinition(WorkloadDefinition):
    """Definition for external workloads."""

    def __init__(
        self,
        metadata: WorkloadMetadata,
        config: dict[str, object],
    ) -> None:
        super().__init__(metadata)
        self._config = config

    @property
    def config(self) -> dict[str, object]:
        return self._config

    def create_workload(
        self,
        model_factory,
        tool_provider,
        system_context,
        session_service,
    ):
        return ExternalAgentWorkload(
            agent_config=self._config,
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            session_service=session_service,
        )


class ExternalDefinitionLoader:
    """Loader for external workload configurations."""

    def can_load(self, path: Path) -> bool:
        """Check if path is an external config file."""
        return path.suffix == ".external" and path.is_file()

    def load(self, path: Path) -> ExternalWorkloadDefinition:
        """Load external workload from path."""
        import yaml

        with path.open() as f:
            config = yaml.safe_load(f)

        metadata = WorkloadMetadata(
            name=config.get("name", path.stem),
            description=config.get("description", ""),
            source_path=path,
            format="external",  # Custom format identifier
        )
        return ExternalWorkloadDefinition(metadata, config)

    def discover(self, directory: Path) -> list[Path]:
        """Discover external config files in directory."""
        return list(directory.rglob("*.external"))

    def load_from_url(self, url: str) -> WorkloadDefinition:
        """HTTP loading not supported for external workloads."""
        msg = "HTTP loading not supported for external workloads"
        raise ValueError(msg)

    def load_from_source(
        self,
        identifier: str,
        base_path: Path | None = None,
    ) -> WorkloadDefinition:
        """Load from any source type."""
        if identifier.startswith(("http://", "https://")):
            return self.load_from_url(identifier)
        path = Path(identifier).expanduser()
        if base_path and not path.is_absolute():
            path = (base_path.parent / path).resolve()
        return self.load(path)
```

### Option 2: Extend WorkloadManager

For full control, extend WorkloadManager to handle your workload type:

```python
from streetrace.workloads.manager import WorkloadManager
from streetrace.workloads.protocol import Workload


class ExtendedWorkloadManager(WorkloadManager):
    """WorkloadManager with custom workload support."""

    def _create_external_workload(
        self,
        config: dict[str, object],
    ) -> Workload:
        """Create external workload from config.

        Args:
            config: External agent configuration

        Returns:
            ExternalAgentWorkload instance

        """
        return ExternalAgentWorkload(
            agent_config=config,
            model_factory=self.model_factory,
            tool_provider=self.tool_provider,
            system_context=self.system_context,
            session_service=self.session_service,
        )
```

## Best Practices

### Resource Management

Always implement proper cleanup in `close()`:

```python
async def close(self) -> None:
    """Clean up all resources."""
    # Close any open connections
    if self._connection:
        await self._connection.close()
        self._connection = None

    # Clean up created agents
    for agent in self._created_agents:
        await self._cleanup_agent(agent)
    self._created_agents.clear()

    # Release any held locks
    if self._lock.locked():
        self._lock.release()
```

### Event Yielding

Yield events as they occur, not in batches:

```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]:
    """Execute with proper event streaming."""
    # Good: Yield events as they occur
    async for event in self._execute(session, message):
        yield event

    # Bad: Collect and yield at end
    # events = []
    # async for event in self._execute(session, message):
    #     events.append(event)
    # for event in events:
    #     yield event
```

### Error Handling

Let exceptions propagate for proper error handling by Supervisor:

```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]:
    """Execute with proper error handling."""
    try:
        async for event in self._execute(session, message):
            yield event
    except SpecificError as e:
        # Transform to appropriate error if needed
        logger.exception("Execution failed")
        raise WorkloadExecutionError(str(e)) from e
    # Let other exceptions propagate naturally
```

### Lazy Agent Creation

Create agents lazily to improve startup performance:

```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]:
    """Execute with lazy agent creation."""
    # Create agent only when first needed
    if self._agent is None:
        self._agent = await self._create_agent()

    # Continue with execution...
```

### Session Handling

Always use the provided session for conversation persistence:

```python
async def run_async(
    self,
    session: Session,
    message: Content | None,
) -> AsyncGenerator[Event, None]:
    """Execute with proper session handling."""
    runner = Runner(
        app_name=session.app_name,  # Use session's app name
        session_service=self._session_service,
        agent=self._agent,
    )

    async for event in runner.run_async(
        user_id=session.user_id,  # Use session's user ID
        session_id=session.id,    # Use session's ID
        new_message=message,
    ):
        yield event
```

## Testing Workloads

### Unit Testing

Test workload behavior in isolation:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from my_workloads import ExternalAgentWorkload


class TestExternalAgentWorkload:
    """Tests for ExternalAgentWorkload."""

    @pytest.fixture
    def mock_session_service(self):
        """Create mock session service."""
        return MagicMock()

    @pytest.fixture
    def workload(self, mock_session_service):
        """Create workload for testing."""
        return ExternalAgentWorkload(
            agent_config={"name": "test", "model": "test-model"},
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=mock_session_service,
        )

    @pytest.mark.asyncio
    async def test_close_cleans_up_agent(self, workload):
        """Test that close cleans up agent resources."""
        workload._agent = MagicMock()

        await workload.close()

        assert workload._agent is None
```

### Integration Testing

Test workload integration with the system:

```python
@pytest.mark.asyncio
async def test_workload_with_supervisor(
    workload_manager,
    session_manager,
    ui_bus,
):
    """Test workload execution through Supervisor."""
    from streetrace.workflow.supervisor import Supervisor

    supervisor = Supervisor(
        workload_manager=workload_manager,
        session_manager=session_manager,
        ui_bus=ui_bus,
    )

    ctx = InputContext(user_input="Hello", agent_name="external_agent")
    result = await supervisor.handle(ctx)

    assert result == HANDLED_CONT
    assert ctx.final_response is not None
```

## Common Patterns

### Composition Pattern

Use composition to reuse existing agent creation logic:

```python
class ComposedWorkload:
    """Workload using composition for agent creation."""

    def __init__(
        self,
        base_agent_def: StreetRaceAgent,
        ...
    ) -> None:
        self._base_agent_def = base_agent_def

    async def _create_agent(self, name: str) -> BaseAgent:
        """Create agent using base definition."""
        # Delegate to existing implementation
        return await self._base_agent_def.create_agent(
            self._model_factory,
            self._tool_provider,
            self._system_context,
        )
```

### Nested Execution Pattern

For workloads that call other workloads:

```python
async def run_agent(self, agent_name: str, *args: object) -> object:
    """Run a nested agent within this workload."""
    agent = await self._create_agent(agent_name)

    # Use isolated session for nested runs
    nested_session_service = InMemorySessionService()
    runner = Runner(
        app_name="nested_execution",
        session_service=nested_session_service,
        agent=agent,
    )

    final_response = None
    async for event in runner.run_async(
        user_id="nested_user",
        session_id="nested_session",
        new_message=content,
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text
            break

    return final_response
```

## See Also

- [Architecture](architecture.md) - Design overview and component relationships
- [API Reference](api-reference.md) - Complete API documentation
- [DSL Runtime](../dsl/architecture.md) - DslAgentWorkflow implementation details
