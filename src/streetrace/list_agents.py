"""List and display available agents."""

from typing import TYPE_CHECKING

from rich.table import Table

from streetrace.ui.render_protocol import register_renderer
from streetrace.ui.ui_bus import UiBus
from streetrace.workloads.definition import WorkloadDefinition

if TYPE_CHECKING:
    from rich.console import Console

    from streetrace.workloads import WorkloadManager


class WorkloadDefinitionList(list[WorkloadDefinition]):
    """A list of WorkloadDefinition objects."""


@register_renderer
def render_workload_definition_list(
    obj: WorkloadDefinitionList,
    console: "Console",
) -> None:
    """Render a list of WorkloadDefinition objects as a formatted table."""
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

    for definition in obj:
        location = (
            str(definition.metadata.source_path)
            if definition.metadata.source_path
            else "Built-in"
        )
        table.add_row(
            definition.name,
            definition.metadata.format,
            definition.metadata.description,
            location,
        )

    console.print(table)


def list_available_agents(workload_manager: "WorkloadManager", ui: UiBus) -> None:
    """Discover and return all available agents/workloads."""
    ui.dispatch_ui_update(
        WorkloadDefinitionList(workload_manager.discover_definitions()),
    )
