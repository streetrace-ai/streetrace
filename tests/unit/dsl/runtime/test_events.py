"""Unit tests for FlowEvent classes.

Test the event dataclass hierarchy for non-ADK operations in DSL workflows.
"""


from streetrace.dsl.runtime.events import (
    FlowEvent,
    LlmCallEvent,
    LlmResponseEvent,
)


class TestFlowEvent:
    """Test the FlowEvent base class."""

    def test_flow_event_requires_type(self):
        """Test that FlowEvent requires a type field."""
        event = FlowEvent(type="custom")
        assert event.type == "custom"

    def test_flow_event_type_is_discriminator(self):
        """Test that type field serves as discriminator."""
        event = FlowEvent(type="test_type")
        assert hasattr(event, "type")
        assert event.type == "test_type"


class TestLlmCallEvent:
    """Test the LlmCallEvent dataclass."""

    def test_llm_call_event_creation(self):
        """Test creating LlmCallEvent with required fields."""
        event = LlmCallEvent(
            prompt_name="analyze",
            model="gpt-4",
            prompt_text="Analyze this input",
        )

        assert event.prompt_name == "analyze"
        assert event.model == "gpt-4"
        assert event.prompt_text == "Analyze this input"

    def test_llm_call_event_type_is_automatic(self):
        """Test that type field is automatically set to 'llm_call'."""
        event = LlmCallEvent(
            prompt_name="test",
            model="claude-3",
            prompt_text="Test prompt",
        )

        assert event.type == "llm_call"

    def test_llm_call_event_type_cannot_be_overridden_at_init(self):
        """Test that type field ignores init value (init=False)."""
        # The type field should always be "llm_call" regardless of what we pass
        event = LlmCallEvent(
            prompt_name="test",
            model="claude-3",
            prompt_text="Test prompt",
        )

        # Type should be the default value, not overrideable
        assert event.type == "llm_call"

    def test_llm_call_event_is_flow_event(self):
        """Test that LlmCallEvent is a subclass of FlowEvent."""
        event = LlmCallEvent(
            prompt_name="test",
            model="gpt-4",
            prompt_text="Test prompt",
        )

        assert isinstance(event, FlowEvent)

    def test_llm_call_event_with_empty_prompt(self):
        """Test LlmCallEvent with empty prompt text."""
        event = LlmCallEvent(
            prompt_name="empty",
            model="gpt-4",
            prompt_text="",
        )

        assert event.prompt_text == ""


class TestLlmResponseEvent:
    """Test the LlmResponseEvent dataclass."""

    def test_llm_response_event_creation(self):
        """Test creating LlmResponseEvent with required fields."""
        event = LlmResponseEvent(
            prompt_name="analyze",
            content="The analysis shows...",
        )

        assert event.prompt_name == "analyze"
        assert event.content == "The analysis shows..."

    def test_llm_response_event_type_is_automatic(self):
        """Test that type field is automatically set to 'llm_response'."""
        event = LlmResponseEvent(
            prompt_name="test",
            content="Response content",
        )

        assert event.type == "llm_response"

    def test_llm_response_event_is_final_by_default(self):
        """Test that is_final defaults to True."""
        event = LlmResponseEvent(
            prompt_name="test",
            content="Response content",
        )

        assert event.is_final is True

    def test_llm_response_event_is_final_can_be_set(self):
        """Test that is_final can be explicitly set to False."""
        event = LlmResponseEvent(
            prompt_name="test",
            content="Partial response",
            is_final=False,
        )

        assert event.is_final is False

    def test_llm_response_event_is_flow_event(self):
        """Test that LlmResponseEvent is a subclass of FlowEvent."""
        event = LlmResponseEvent(
            prompt_name="test",
            content="Response",
        )

        assert isinstance(event, FlowEvent)

    def test_llm_response_event_with_empty_content(self):
        """Test LlmResponseEvent with empty content."""
        event = LlmResponseEvent(
            prompt_name="empty",
            content="",
        )

        assert event.content == ""

    def test_llm_response_event_with_multiline_content(self):
        """Test LlmResponseEvent with multiline content."""
        multiline = "Line 1\nLine 2\nLine 3"
        event = LlmResponseEvent(
            prompt_name="multiline",
            content=multiline,
        )

        assert event.content == multiline


class TestEventHierarchy:
    """Test the event class hierarchy relationships."""

    def test_isinstance_checks_for_flow_events(self):
        """Test that isinstance works correctly for all event types."""
        llm_call = LlmCallEvent(
            prompt_name="test",
            model="gpt-4",
            prompt_text="Test",
        )
        llm_response = LlmResponseEvent(
            prompt_name="test",
            content="Response",
        )

        # Both should be FlowEvent instances
        assert isinstance(llm_call, FlowEvent)
        assert isinstance(llm_response, FlowEvent)

        # Each should be its own type
        assert isinstance(llm_call, LlmCallEvent)
        assert isinstance(llm_response, LlmResponseEvent)

        # But not each other's type
        assert not isinstance(llm_call, LlmResponseEvent)
        assert not isinstance(llm_response, LlmCallEvent)

    def test_type_discriminator_uniqueness(self):
        """Test that event types have unique discriminator values."""
        llm_call = LlmCallEvent(
            prompt_name="test",
            model="gpt-4",
            prompt_text="Test",
        )
        llm_response = LlmResponseEvent(
            prompt_name="test",
            content="Response",
        )

        assert llm_call.type != llm_response.type
        assert llm_call.type == "llm_call"
        assert llm_response.type == "llm_response"

    def test_events_are_dataclasses(self):
        """Test that event classes are proper dataclasses."""
        from dataclasses import fields

        # FlowEvent should have a 'type' field
        flow_fields = {f.name for f in fields(FlowEvent)}
        assert "type" in flow_fields

        # LlmCallEvent should have its specific fields
        call_fields = {f.name for f in fields(LlmCallEvent)}
        assert "prompt_name" in call_fields
        assert "model" in call_fields
        assert "prompt_text" in call_fields
        assert "type" in call_fields

        # LlmResponseEvent should have its specific fields
        response_fields = {f.name for f in fields(LlmResponseEvent)}
        assert "prompt_name" in response_fields
        assert "content" in response_fields
        assert "is_final" in response_fields
        assert "type" in response_fields
