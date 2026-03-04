"""Test Supervisor FlowEvent handling.

Test the Supervisor's ability to handle both ADK Events and FlowEvents,
dispatching them appropriately to the UI bus and capturing final responses.
"""

import pytest

from streetrace.dsl.runtime.events import FlowEvent, LlmCallEvent, LlmResponseEvent
from streetrace.input_handler import InputContext
from streetrace.ui.adk_event_renderer import Event
from streetrace.workflow.supervisor import Supervisor


class TestSupervisorFlowEventHandling:
    """Test Supervisor handling of FlowEvent types."""

    @pytest.mark.asyncio
    async def test_flow_event_dispatched_directly_to_ui_bus(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
    ) -> None:
        """Test that FlowEvent is dispatched directly to UI bus without wrapping."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        flow_event = LlmCallEvent(
            prompt_name="test_prompt",
            model="test-model",
            prompt_text="Hello world",
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([flow_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - FlowEvent should be dispatched directly (not wrapped in Event)
        dispatch_calls = mock_ui_bus.dispatch_ui_update.call_args_list
        assert len(dispatch_calls) == 1
        dispatched_event = dispatch_calls[0][0][0]
        assert isinstance(dispatched_event, LlmCallEvent)
        assert dispatched_event is flow_event

    @pytest.mark.asyncio
    async def test_llm_response_event_captures_final_response(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
    ) -> None:
        """Test that LlmResponseEvent with is_final=True captures final response."""
        # Arrange
        expected_response = "This is the LLM response content."
        input_context = InputContext(user_input="Test prompt")
        llm_response = LlmResponseEvent(
            prompt_name="test_prompt",
            content=expected_response,
            is_final=True,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([llm_response])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert
        assert input_context.final_response == expected_response

    @pytest.mark.asyncio
    async def test_llm_response_event_non_final_does_not_capture_response(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
    ) -> None:
        """Test that LlmResponseEvent with is_final=False does not capture response."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        llm_response = LlmResponseEvent(
            prompt_name="test_prompt",
            content="Intermediate response",
            is_final=False,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([llm_response])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Should have default message since is_final=False
        assert input_context.final_response == "Agent did not produce a final response."

    @pytest.mark.asyncio
    async def test_adk_event_wrapped_in_event_class(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
        events_mocker,
    ) -> None:
        """Test that ADK Event is wrapped in Event class before dispatching."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        adk_event = events_mocker(
            content="Final response from ADK",
            is_final_response=True,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([adk_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - ADK event should be wrapped in Event class
        dispatch_calls = mock_ui_bus.dispatch_ui_update.call_args_list
        assert len(dispatch_calls) == 1
        dispatched_event = dispatch_calls[0][0][0]
        assert isinstance(dispatched_event, Event)
        assert dispatched_event.event is adk_event

    @pytest.mark.asyncio
    async def test_mixed_flow_and_adk_events(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
        events_mocker,
    ) -> None:
        """Test handling mixed stream of FlowEvents and ADK Events."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        # Create mixed events
        llm_call = LlmCallEvent(
            prompt_name="prompt1",
            model="model1",
            prompt_text="First prompt",
        )
        llm_response = LlmResponseEvent(
            prompt_name="prompt1",
            content="LLM response",
            is_final=True,
        )
        adk_event = events_mocker(
            content="ADK intermediate",
            is_final_response=False,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([
            llm_call,
            adk_event,
            llm_response,
        ])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - All events dispatched in order
        dispatch_calls = mock_ui_bus.dispatch_ui_update.call_args_list
        assert len(dispatch_calls) == 3

        # LlmCallEvent dispatched directly (not wrapped)
        assert isinstance(dispatch_calls[0][0][0], LlmCallEvent)

        # ADK event wrapped in Event class
        assert isinstance(dispatch_calls[1][0][0], Event)

        # LlmResponseEvent dispatched directly (not wrapped)
        assert isinstance(dispatch_calls[2][0][0], LlmResponseEvent)

        # Final response captured from LlmResponseEvent
        assert input_context.final_response == "LLM response"

    @pytest.mark.asyncio
    async def test_adk_final_response_takes_precedence_when_first(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
        events_mocker,
    ) -> None:
        """Test that first final response (ADK or Flow) wins."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        adk_event = events_mocker(
            content="ADK final response",
            is_final_response=True,
        )
        llm_response = LlmResponseEvent(
            prompt_name="prompt1",
            content="LLM final response",
            is_final=True,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([
            adk_event,
            llm_response,
        ])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - ADK event came first, so its response is captured
        assert input_context.final_response == "ADK final response"

    @pytest.mark.asyncio
    async def test_flow_event_final_response_takes_precedence_when_first(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
        events_mocker,
    ) -> None:
        """Test that first final response (ADK or Flow) wins."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")

        llm_response = LlmResponseEvent(
            prompt_name="prompt1",
            content="LLM final response",
            is_final=True,
        )
        adk_event = events_mocker(
            content="ADK final response",
            is_final_response=True,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([
            llm_response,
            adk_event,
        ])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - LLM response came first, so its response is captured
        assert input_context.final_response == "LLM final response"

    @pytest.mark.asyncio
    async def test_session_manager_called_only_for_adk_events(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
    ) -> None:
        """Test that manage_current_session is not called for FlowEvents."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        flow_event = LlmCallEvent(
            prompt_name="test_prompt",
            model="test-model",
            prompt_text="Hello world",
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([flow_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - manage_current_session should NOT be called for FlowEvent
        mock_session_manager.manage_current_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_manager_called_for_adk_events(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
        events_mocker,
    ) -> None:
        """Test that session_manager.manage_current_session is called for ADK events."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        adk_event = events_mocker(
            content="Final response",
            is_final_response=True,
        )

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([adk_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - manage_current_session should be called for ADK event
        mock_session_manager.manage_current_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_base_flow_event_dispatched_directly(
        self,
        mock_session_manager,
        mock_workload_manager,
        shallow_supervisor: Supervisor,
        mock_session,
        mock_workload,
        mock_ui_bus,
    ) -> None:
        """Test that base FlowEvent class is also dispatched directly."""
        # Arrange
        input_context = InputContext(user_input="Test prompt")
        # Create a base FlowEvent (not a subclass)
        flow_event = FlowEvent(type="custom_event")

        shallow_supervisor.session_manager = mock_session_manager
        shallow_supervisor.workload_manager = mock_workload_manager
        shallow_supervisor.ui_bus = mock_ui_bus
        shallow_supervisor.session_manager.validate_session.return_value = mock_session

        mock_workload.run_async.return_value = self._async_iter([flow_event])

        # Act
        await shallow_supervisor.handle(input_context)

        # Assert - Base FlowEvent should be dispatched directly
        dispatch_calls = mock_ui_bus.dispatch_ui_update.call_args_list
        assert len(dispatch_calls) == 1
        dispatched_event = dispatch_calls[0][0][0]
        assert isinstance(dispatched_event, FlowEvent)
        assert dispatched_event is flow_event

    @staticmethod
    async def _async_iter(items: list) -> list:
        """Create an async generator from a list."""
        for item in items:
            yield item
