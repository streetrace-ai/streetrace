# Task Definition: ADK Event Escalation Integration

## Feature Information

- **Feature ID**: 017-dsl
- **Task ID**: escalation-operator/adk-integration
- **Branch**: feature/017-streetrace-dsl-2

## Summary

Integrate the DSL escalation feature with ADK's native `Event.actions.escalate` flag so that
parent agents in a hierarchy can see the escalation signal through the ADK event system.

## Context

The ADK Event system has a native escalation signal:
```python
# In google.adk.events.event_actions.EventActions
escalate: Optional[bool] = None
"""The agent is escalating to a higher level agent."""
```

Currently `run_agent_with_escalation()` sets an internal `_last_escalated` flag but doesn't
propagate escalation through the ADK event system. This means parent agents won't see the
escalation signal.

## Design Decision

After analyzing the codebase patterns, we will use the **FlowEvent approach** rather than
creating ADK Event objects directly. This is because:

1. The codebase already has a clean separation between ADK events and FlowEvents
2. FlowEvents are used for non-ADK operations (like `LlmCallEvent`, `LlmResponseEvent`)
3. Creating ADK Event objects requires more complex setup (author, invocation_id, etc.)
4. The EscalationEvent pattern is simpler and keeps escalation events clearly identifiable

## Solution

When escalation is detected, yield an `EscalationEvent` (a new FlowEvent type) that signals
escalation occurred. This integrates with the existing event system and allows parent flows
to react to escalation.

## Implementation Requirements

1. Add `EscalationEvent` dataclass to `events.py`
2. Update `run_agent_with_escalation()` in `context.py` to yield `EscalationEvent` when triggered
3. Ensure the event is yielded AFTER all agent events have been processed
4. Maintain backward compatibility - existing code should continue to work

## Success Criteria

- When escalation is triggered, an `EscalationEvent` is yielded after agent events
- When escalation is not triggered, no extra event is yielded
- The escalation event contains agent name, result, and condition information
- All existing escalation tests continue to pass
- New tests verify the event yielding behavior
