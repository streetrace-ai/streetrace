"""List and display available agents."""

from typing import TYPE_CHECKING

from rich.table import Table

from streetrace.agents.base_agent_loader import AgentInfo
from streetrace.ui.render_protocol import register_renderer
from streetrace.ui.ui_bus import UiBus

if TYPE_CHECKING:
    from rich.console import Console

    from streetrace.agents.agent_manager import AgentManager


class AgentInfoList(list[AgentInfo]):
    """A list of AgentInfo objects."""


@register_renderer
def render_agent_info_list(obj: AgentInfoList, console: "Console") -> None:
    """Render a list of AgentInfo objects as a formatted table."""
    if not obj:
        console.print("[yellow]No agents found.[/yellow]")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        show_edge=False,
        show_lines=False,
        box=None,
    )
    table.add_column("Name", style="green")
    table.add_column("Type", justify="center")
    table.add_column("Description", style="dim")
    table.add_column("Location", style="blue", no_wrap=False)

    for agent in obj:
        location = str(agent.file_path) if agent.file_path else "Built-in"
        table.add_row(
            agent.name,
            agent.kind,
            agent.description,
            location,
        )

    console.print(table)


def list_available_agents(agent_manager: "AgentManager", ui: UiBus) -> None:
    """Discover and return all available agents."""
    ui.dispatch_ui_update(AgentInfoList(agent_manager.discover()))
