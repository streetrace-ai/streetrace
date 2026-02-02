"""Integration tests for parallel block execution.

Test that parallel blocks compile and execute correctly using
ADK's ParallelAgent for concurrent agent execution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.dsl.ast import (
    AgentDef,
    DslFile,
    FlowDef,
    ParallelBlock,
    PromptDef,
    ReturnStmt,
    RunStmt,
    ToolDef,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestParallelBlockExecution:
    """Test parallel block execution."""

    def test_parallel_block_code_compiles_and_creates_class(self) -> None:
        """Parallel block generated code can be compiled to create a class."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(
                                    target="a",
                                    agent="task_a",
                                    input=VarRef(name="input_prompt"),
                                ),
                                RunStmt(
                                    target="b",
                                    agent="task_b",
                                    input=VarRef(name="input_prompt"),
                                ),
                            ],
                        ),
                        ReturnStmt(value=VarRef(name="a")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code compiles
        compiled = compile(code, "<generated>", "exec")
        assert compiled is not None

        # Verify the generated code creates the expected class structure
        # The class should be named TestWorkflow (from test.sr filename)
        assert "class TestWorkflow" in code
        assert "_execute_parallel_agents" in code

    @pytest.mark.asyncio
    async def test_execute_parallel_agents_uses_parallel_agent(self) -> None:
        """_execute_parallel_agents uses ADK ParallelAgent."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        # Create mock agent factory
        mock_agent_factory = MagicMock()

        # Create mock agents that will be returned
        mock_agent_a = MagicMock()
        mock_agent_a.name = "agent_a"
        mock_agent_b = MagicMock()
        mock_agent_b.name = "agent_b"

        # Track which output_keys were used
        created_agents: list[tuple[str, str | None]] = []

        async def mock_create_agent(
            agent_name: str,
            model_factory: object,  # noqa: ARG001
            tool_provider: object,  # noqa: ARG001
            system_context: object,  # noqa: ARG001
            *,
            output_key: str | None = None,
        ) -> MagicMock:
            """Track agent creation with output_key."""
            created_agents.append((agent_name, output_key))
            if agent_name == "agent_a":
                return mock_agent_a
            return mock_agent_b

        mock_agent_factory.create_agent = mock_create_agent

        # Create workflow with mocked dependencies
        workflow = DslAgentWorkflow(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
            agent_factory=mock_agent_factory,
        )

        # Create context
        ctx = WorkflowContext(workflow=workflow)

        # Create mock session with state containing results
        mock_session = MagicMock()
        mock_session.state = {}

        # Create mock session service
        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        # Create mock runner that populates session state and yields events
        async def mock_run_async_gen(*args: object, **kwargs: object):  # noqa: ARG001
            # Simulate ParallelAgent storing results in session state
            for agent_name, output_key in created_agents:
                if output_key:
                    mock_session.state[output_key] = f"result_{agent_name}"
            # Yield a mock event
            yield MagicMock()

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = mock_run_async_gen

        # Patch the actual import locations (google.adk modules)
        with (
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_session_service,
            ),
            patch(
                "google.adk.Runner",
                return_value=mock_runner_instance,
            ),
            patch(
                "google.adk.agents.ParallelAgent",
            ) as mock_parallel_agent_class,
        ):
            # Execute parallel agents - now an async generator
            specs: list[tuple[str, list[object], str | None]] = [
                ("agent_a", ["arg1"], "var_a"),
                ("agent_b", ["arg2"], "var_b"),
            ]
            events = [
                event
                async for event in workflow._execute_parallel_agents(ctx, specs)  # noqa: SLF001
            ]

            # Verify events were yielded
            assert len(events) == 1

            # Verify ParallelAgent was created with sub_agents
            mock_parallel_agent_class.assert_called_once()
            call_kwargs = mock_parallel_agent_class.call_args.kwargs
            assert "sub_agents" in call_kwargs
            assert len(call_kwargs["sub_agents"]) == 2

            # Verify agents were created with output_keys
            assert len(created_agents) == 2
            agent_a_entry = next(
                (e for e in created_agents if e[0] == "agent_a"),
                None,
            )
            agent_b_entry = next(
                (e for e in created_agents if e[0] == "agent_b"),
                None,
            )
            assert agent_a_entry is not None
            assert agent_a_entry[1] is not None  # output_key should be set
            assert agent_b_entry is not None
            assert agent_b_entry[1] is not None  # output_key should be set

            # Verify results were stored in ctx.vars
            assert ctx.vars["var_a"] == "result_agent_a"
            assert ctx.vars["var_b"] == "result_agent_b"

    @pytest.mark.asyncio
    async def test_execute_parallel_agents_with_none_target(self) -> None:
        """_execute_parallel_agents handles None target variables."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_agent_factory = MagicMock()
        created_agents: list[tuple[str, str | None]] = []

        async def mock_create_agent(
            agent_name: str,
            model_factory: object,  # noqa: ARG001
            tool_provider: object,  # noqa: ARG001
            system_context: object,  # noqa: ARG001
            *,
            output_key: str | None = None,
        ) -> MagicMock:
            """Track agent creation."""
            created_agents.append((agent_name, output_key))
            mock_agent = MagicMock()
            mock_agent.name = agent_name
            return mock_agent

        mock_agent_factory.create_agent = mock_create_agent

        workflow = DslAgentWorkflow(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
            agent_factory=mock_agent_factory,
        )

        ctx = WorkflowContext(workflow=workflow)

        # Create mock session with state
        mock_session = MagicMock()
        mock_session.state = {}

        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def mock_run_async_gen(*args: object, **kwargs: object):  # noqa: ARG001
            # Store results for agents with output_keys
            for agent_name, output_key in created_agents:
                if output_key:
                    mock_session.state[output_key] = f"result_{agent_name}"
            yield MagicMock()

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = mock_run_async_gen

        with (
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_session_service,
            ),
            patch(
                "google.adk.Runner",
                return_value=mock_runner_instance,
            ),
            patch("google.adk.agents.ParallelAgent"),
        ):
            # Execute with None target - result should be omitted from ctx.vars
            specs: list[tuple[str, list[object], str | None]] = [
                ("agent_a", [], "var_a"),
                ("agent_b", [], None),  # No target variable
            ]
            async for _ in workflow._execute_parallel_agents(ctx, specs):  # noqa: SLF001
                pass

            # Only var_a should be in ctx.vars (agent_b had None target)
            assert "var_a" in ctx.vars
            assert ctx.vars["var_a"] == "result_agent_a"

    @pytest.mark.asyncio
    async def test_execute_parallel_agents_empty_specs(self) -> None:
        """_execute_parallel_agents handles empty specs list."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = DslAgentWorkflow(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
            agent_factory=MagicMock(),
        )

        ctx = WorkflowContext(workflow=workflow)

        # Execute with empty specs - should return immediately without yielding
        events = [
            event
            async for event in workflow._execute_parallel_agents(ctx, [])  # noqa: SLF001
        ]

        # Should yield nothing for empty specs
        assert events == []

    @pytest.mark.asyncio
    async def test_execute_parallel_agents_requires_agent_factory(self) -> None:
        """_execute_parallel_agents raises error without agent_factory."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        # Create workflow WITHOUT agent_factory
        workflow = DslAgentWorkflow(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
            agent_factory=None,  # No agent factory
        )

        ctx = WorkflowContext(workflow=workflow)

        specs: list[tuple[str, list[object], str | None]] = [
            ("agent_a", ["arg1"], "var_a"),
        ]

        with pytest.raises(ValueError, match="requires agent_factory"):
            # Must iterate to trigger the generator execution
            async for _ in workflow._execute_parallel_agents(ctx, specs):  # noqa: SLF001
                pass

    @pytest.mark.asyncio
    async def test_execute_parallel_agents_creates_unique_output_keys(self) -> None:
        """_execute_parallel_agents creates unique output_keys for each agent."""
        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        mock_agent_factory = MagicMock()
        output_keys_used: list[str] = []

        async def mock_create_agent(
            agent_name: str,
            model_factory: object,  # noqa: ARG001
            tool_provider: object,  # noqa: ARG001
            system_context: object,  # noqa: ARG001
            *,
            output_key: str | None = None,
        ) -> MagicMock:
            """Track output_keys."""
            if output_key:
                output_keys_used.append(output_key)
            mock_agent = MagicMock()
            mock_agent.name = agent_name
            return mock_agent

        mock_agent_factory.create_agent = mock_create_agent

        workflow = DslAgentWorkflow(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            session_service=MagicMock(),
            agent_factory=mock_agent_factory,
        )

        ctx = WorkflowContext(workflow=workflow)

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def mock_run_async_gen(*args: object, **kwargs: object):  # noqa: ARG001
            yield MagicMock()

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = mock_run_async_gen

        with (
            patch(
                "google.adk.sessions.InMemorySessionService",
                return_value=mock_session_service,
            ),
            patch(
                "google.adk.Runner",
                return_value=mock_runner_instance,
            ),
            patch("google.adk.agents.ParallelAgent"),
        ):
            specs: list[tuple[str, list[object], str | None]] = [
                ("agent_a", [], "var_a"),
                ("agent_b", [], "var_b"),
                ("agent_c", [], "var_c"),
            ]
            async for _ in workflow._execute_parallel_agents(ctx, specs):  # noqa: SLF001
                pass

            # Verify all output_keys are unique
            assert len(output_keys_used) == 3
            assert len(set(output_keys_used)) == 3  # All unique
