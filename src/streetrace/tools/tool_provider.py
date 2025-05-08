"""Provide tools to agents."""

from collections.abc import Callable

from streetrace.tools.fake_tools import get_current_time, get_weather

AnyTool = Callable | None


class ToolProvider:
    """Provides access to requested tools to agents.

    Collects all available tools from all supported sources.
    """

    def get_tool(self, ref: str) -> AnyTool:
        """Return a tool implementation given its reference name."""
        if ref == "get_weather":
            return get_weather
        if ref == "get_current_time":
            return get_current_time
        return None
