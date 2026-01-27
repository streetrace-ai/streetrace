"""Renderers for FlowEvent types.

Provide rendering functions for non-ADK events emitted by DSL flows,
such as direct LLM calls and escalation events.
"""

from typing import TYPE_CHECKING

from streetrace.dsl.runtime.events import (
    EscalationEvent,
    LlmCallEvent,
    LlmResponseEvent,
)
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer

if TYPE_CHECKING:
    from rich.console import Console


@register_renderer
def render_llm_call(obj: LlmCallEvent, console: "Console") -> None:
    """Render LLM call initiation event."""
    console.print(
        f"{obj.prompt_name}: {obj.prompt_text}",
        style=Styles.RICH_INFO,
    )


@register_renderer
def render_llm_response(obj: LlmResponseEvent, console: "Console") -> None:
    """Render LLM response event as markdown."""
    from rich.markdown import Markdown

    console.print(f"[bold]{obj.prompt_name}:[/bold]", style=Styles.RICH_MODEL)
    console.print(
        Markdown(obj.content, inline_code_theme=Styles.RICH_MD_CODE),
        style=Styles.RICH_MODEL,
    )


@register_renderer
def render_escalation_event(obj: EscalationEvent, console: "Console") -> None:
    """Render escalation event showing agent escalation triggered."""
    console.print(
        f"⚡ Escalation: {obj.agent_name} triggered ({obj.condition_op} "
        f'"{obj.condition_value}")',
        style=Styles.RICH_WARNING,
    )
