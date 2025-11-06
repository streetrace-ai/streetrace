"""Agent identifier resolution supporting names, paths, and HTTP URLs."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streetrace.agents.base_agent_loader import AgentInfo

import httpx

from streetrace.log import get_logger

logger = get_logger(__name__)


class SourceType(str, Enum):
    """Type of agent source."""

    DISCOVERED_NAME = "discovered_name"
    FILE_PATH = "file_path"
    HTTP_URL = "http_url"


@dataclass
class AgentResolution:
    """Result of agent identifier resolution.

    Attributes:
        content: Agent YAML content as string
        source: Original identifier or resolved path/URL
        source_type: Type of source that was resolved
        file_path: Path object if source was a file, None otherwise

    """

    content: str
    source: str
    source_type: SourceType
    file_path: Path | None = None


class AgentResolver:
    """Resolves agent identifiers to YAML content.

    Supports:
    - Discovered agent names (from agent discovery)
    - File system paths (absolute, ~/, relative)
    - HTTP/HTTPS URLs with optional authentication
    """

    def __init__(
        self,
        discovered_agents: list["AgentInfo"] | None = None,
        http_auth: str | None = None,
    ) -> None:
        """Initialize the agent resolver.

        Args:
            discovered_agents: List of discovered agents for name resolution
            http_auth: Authorization header value for HTTP requests

        """
        self.discovered_agents = discovered_agents or []
        self.http_auth = http_auth

    def resolve(self, identifier: str, base_path: Path | None = None) -> AgentResolution:
        """Resolve an agent identifier to YAML content.

        Resolution order:
        1. Check if it's an HTTP(S) URL
        2. Check if it's a file path (absolute, ~/, or relative)
        3. Check if it matches a discovered agent name

        Args:
            identifier: Agent identifier (name, path, or URL)
            base_path: Base path for resolving relative paths

        Returns:
            AgentResolution with content and metadata

        Raises:
            ValueError: If identifier cannot be resolved

        """
        identifier = identifier.strip()

        # 1. Try HTTP URL
        if identifier.startswith(("http://", "https://")):
            return self._resolve_http(identifier)

        # 2. Try file path
        file_path = self._try_resolve_path(identifier, base_path)
        if file_path and file_path.exists():
            return self._resolve_file(file_path)

        # 3. Try discovered agent name
        agent_info = self._find_discovered_agent(identifier)
        if agent_info and agent_info.file_path and agent_info.file_path.exists():
            return self._resolve_file(agent_info.file_path)

        # Failed to resolve
        msg = (
            f"Could not resolve agent identifier '{identifier}'. "
            "Not found as HTTP URL, file path, or discovered agent name."
        )
        raise ValueError(msg)

    def _resolve_http(self, url: str) -> AgentResolution:
        """Fetch agent YAML from HTTP URL.

        Args:
            url: HTTP(S) URL to fetch

        Returns:
            AgentResolution with fetched content

        Raises:
            ValueError: If HTTP request fails

        """
        headers = {"Accept": "application/x-yaml, application/yaml, text/yaml"}
        if self.http_auth:
            headers["Authorization"] = self.http_auth

        try:
            response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            content = response.text
            logger.info("Fetched agent from HTTP URL: %s", url)
            return AgentResolution(
                content=content,
                source=url,
                source_type=SourceType.HTTP_URL,
                file_path=None,
            )
        except httpx.HTTPError as e:
            msg = f"Failed to fetch agent from {url}: {e}"
            raise ValueError(msg) from e

    def _resolve_file(self, file_path: Path) -> AgentResolution:
        """Read agent YAML from file.

        Args:
            file_path: Path to YAML file

        Returns:
            AgentResolution with file content

        Raises:
            ValueError: If file cannot be read

        """
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Loaded agent from file: %s", file_path)
            return AgentResolution(
                content=content,
                source=str(file_path),
                source_type=SourceType.FILE_PATH,
                file_path=file_path,
            )
        except OSError as e:
            msg = f"Failed to read agent file {file_path}: {e}"
            raise ValueError(msg) from e

    def _try_resolve_path(self, identifier: str, base_path: Path | None) -> Path | None:
        """Try to resolve identifier as a file path.

        Args:
            identifier: Potential file path
            base_path: Base path for relative resolution

        Returns:
            Resolved Path or None if not a valid path

        """
        # Absolute path
        if identifier.startswith("/"):
            return Path(identifier)

        # Home directory
        if identifier.startswith("~/"):
            return Path(identifier).expanduser().resolve()

        # Relative path
        if base_path:
            return (base_path.parent / identifier).resolve()

        # Try relative to cwd
        return Path(identifier).resolve()

    def _find_discovered_agent(self, name: str) -> "AgentInfo | None":
        """Find agent by name in discovered agents.

        Args:
            name: Agent name to find

        Returns:
            AgentInfo if found, None otherwise

        """
        name_lower = name.lower()
        for agent in self.discovered_agents:
            if agent.name.lower() == name_lower:
                return agent
        return None

