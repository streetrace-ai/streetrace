"""Source identifier resolution supporting names, paths, and HTTP URLs.

This module provides format-agnostic resolution of identifiers to raw content.
It can be used for YAML, Markdown, or any other text-based agent definitions.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

import httpx

from streetrace.log import get_logger

logger = get_logger(__name__)


class SourceType(str, Enum):
    """Type of source."""

    DISCOVERED_NAME = "discovered_name"
    FILE_PATH = "file_path"
    HTTP_URL = "http_url"


@dataclass
class SourceResolution:
    """Result of source identifier resolution.

    Attributes:
        content: Raw content as string (format-agnostic)
        source: Original identifier or resolved path/URL
        source_type: Type of source that was resolved
        file_path: Path object if source was a file, None otherwise
        content_type: MIME type from HTTP response, if available
        format: Detected format ("dsl", "yaml", "python") or None if unknown

    """

    content: str
    source: str
    source_type: SourceType
    file_path: Path | None = None
    content_type: str | None = None
    format: str | None = None


class SourceResolver:
    """Resolves identifiers to raw content with format detection.

    Supports:
    - Discovered source names (from discovery, mapped to paths)
    - File system paths (absolute, ~/, relative)
    - HTTP/HTTPS URLs with optional authentication (YAML only)

    Also provides:
    - Format detection from file extension or MIME type
    - Discovery of agents in search locations
    - Security policy enforcement for HTTP sources
    """

    # Directories to exclude from discovery
    EXCLUDED_DIRS: ClassVar[set[str]] = {
        ".venv",
        ".git",
        ".github",
        "node_modules",
        "__pycache__",
    }

    # MIME types that indicate YAML content
    YAML_MIME_TYPES: ClassVar[set[str]] = {
        "application/yaml",
        "application/x-yaml",
        "text/yaml",
        "text/x-yaml",
    }

    def __init__(
        self,
        discovered_sources: dict[str, Path] | None = None,
        http_auth: str | None = None,
    ) -> None:
        """Initialize the source resolver.

        Args:
            discovered_sources: Mapping of names to file paths for name resolution
            http_auth: Authorization header value for HTTP requests

        """
        self.discovered_sources = discovered_sources or {}
        self.http_auth = http_auth

    def resolve(
        self,
        identifier: str,
        base_path: Path | None = None,
        accept_types: list[str] | None = None,
    ) -> SourceResolution:
        """Resolve an identifier to raw content.

        Resolution order:
        1. Check if it's an HTTP(S) URL
        2. Check if it's a file path (absolute, ~/, or relative)
        3. Check if it matches a discovered source name

        Args:
            identifier: Source identifier (name, path, or URL)
            base_path: Base path for resolving relative paths
            accept_types: MIME types to accept for HTTP requests

        Returns:
            SourceResolution with content and metadata

        Raises:
            ValueError: If identifier cannot be resolved

        """
        identifier = identifier.strip()

        # 1. Try HTTP URL
        if identifier.startswith(("http://", "https://")):
            return self._resolve_http(identifier, accept_types)

        # 2. Try file path
        file_path = self._try_resolve_path(identifier, base_path)
        if file_path and file_path.exists():
            return self._resolve_file(file_path)

        # 3. Try discovered source name
        discovered_path = self._find_discovered_source(identifier)
        if discovered_path and discovered_path.exists():
            return self._resolve_file(discovered_path)

        # Failed to resolve
        msg = (
            f"Could not resolve identifier '{identifier}'. "
            "Not found as HTTP URL, file path, or discovered source name."
        )
        raise ValueError(msg)

    def _resolve_http(
        self,
        url: str,
        accept_types: list[str] | None = None,
    ) -> SourceResolution:
        """Fetch content from HTTP URL.

        Security Policy:
        - Python (.py) files are rejected - code import risk
        - YAML and DSL are allowed over HTTP (DSL is compiled before execution)

        Args:
            url: HTTP(S) URL to fetch
            accept_types: MIME types to accept (default: text/plain, text/yaml)

        Returns:
            SourceResolution with fetched content and format

        Raises:
            ValueError: If URL is rejected by security policy or HTTP request fails

        """
        # Security policy: reject Python over HTTP (requires import)
        url_lower = url.lower()
        if url_lower.endswith(".py") or "/agent.py" in url_lower:
            msg = (
                f"HTTP loading is not supported for Python agents: {url}. "
                "Python agents must be loaded from the local filesystem."
            )
            raise ValueError(msg)

        if accept_types is None:
            accept_types = [
                "text/plain",
                "application/x-yaml",
                "application/yaml",
                "text/yaml",
            ]

        headers = {"Accept": ", ".join(accept_types)}
        if self.http_auth:
            headers["Authorization"] = self.http_auth

        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            content = response.text
            content_type = response.headers.get("Content-Type")

            # Detect format from MIME type or URL extension
            detected_format = self._detect_format_from_http(url, content_type)

            logger.info(
                "Fetched content from HTTP URL: %s (format=%s)", url, detected_format,
            )
            return SourceResolution(
                content=content,
                source=url,
                source_type=SourceType.HTTP_URL,
                file_path=None,
                content_type=content_type,
                format=detected_format,
            )
        except httpx.HTTPError as e:
            msg = f"Failed to fetch content from {url}: {e}"
            raise ValueError(msg) from e

    def _resolve_file(self, file_path: Path) -> SourceResolution:
        """Read content from file with format detection.

        Args:
            file_path: Path to file (or directory for Python agents)

        Returns:
            SourceResolution with file content and detected format

        Raises:
            ValueError: If file cannot be read

        """
        # Handle Python agent directories
        if file_path.is_dir():
            agent_file = file_path / "agent.py"
            if agent_file.exists():
                # For Python agents, we read agent.py but the path is the directory
                try:
                    content = agent_file.read_text(encoding="utf-8")
                    logger.debug("Loaded Python agent from directory: %s", file_path)
                    return SourceResolution(
                        content=content,
                        source=str(file_path),
                        source_type=SourceType.FILE_PATH,
                        file_path=file_path,
                        format="python",
                    )
                except OSError as e:
                    msg = f"Failed to read agent.py from {file_path}: {e}"
                    raise ValueError(msg) from e
            else:
                msg = f"Directory {file_path} does not contain agent.py"
                raise ValueError(msg)

        # Regular file
        try:
            content = file_path.read_text(encoding="utf-8")
            detected_format = self._detect_format_from_path(file_path)
            logger.debug(
                "Loaded content from file: %s (format=%s)", file_path, detected_format,
            )
            return SourceResolution(
                content=content,
                source=str(file_path),
                source_type=SourceType.FILE_PATH,
                file_path=file_path,
                format=detected_format,
            )
        except OSError as e:
            msg = f"Failed to read file {file_path}: {e}"
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

    def _find_discovered_source(self, name: str) -> Path | None:
        """Find source path by name in discovered sources.

        Args:
            name: Source name to find

        Returns:
            Path if found, None otherwise

        """
        name_lower = name.lower()
        return self.discovered_sources.get(name_lower)

    def _detect_format_from_path(self, path: Path) -> str | None:
        """Detect format from file extension.

        Args:
            path: Path to file

        Returns:
            Format string ("dsl", "yaml", "python") or None if unknown

        """
        suffix = path.suffix.lower()
        if suffix == ".sr":
            return "dsl"
        if suffix in (".yaml", ".yml"):
            return "yaml"
        if suffix == ".py":
            return "python"
        return None

    def _detect_format_from_http(
        self,
        url: str,
        content_type: str | None,
    ) -> str | None:
        """Detect format from HTTP response MIME type or URL extension.

        Priority:
        1. URL extension (.sr → dsl, .yaml/.yml → yaml)
        2. MIME type (if YAML MIME, return yaml)
        3. Default to DSL for other content

        Args:
            url: The HTTP URL
            content_type: Content-Type header from response

        Returns:
            Format string ("yaml" or "dsl") or None

        """
        # Check URL extension first (most explicit)
        url_lower = url.lower()
        if url_lower.endswith(".sr"):
            return "dsl"
        if url_lower.endswith((".yaml", ".yml")):
            return "yaml"

        # Check MIME type
        if content_type:
            # Extract MIME type without parameters (e.g., charset)
            mime_type = content_type.split(";")[0].strip().lower()
            if mime_type in self.YAML_MIME_TYPES:
                return "yaml"

        # Default: treat as DSL
        return "dsl"

    def _is_excluded(self, path: Path) -> bool:
        """Check if path should be excluded from discovery.

        Excludes files in:
        - Hidden directories (starting with .)
        - Directories in EXCLUDED_DIRS

        Args:
            path: Path to check

        Returns:
            True if path should be excluded

        """
        for part in path.parts:
            # Exclude hidden directories (starting with .)
            if part.startswith(".") and part not in {".", ".."}:
                return True
            # Exclude specific directories
            if part in self.EXCLUDED_DIRS:
                return True
        return False

    def discover(self, locations: list[Path]) -> dict[str, SourceResolution]:
        """Discover all agents in the given locations.

        Searches for:
        - .sr files (DSL agents)
        - .yaml and .yml files (YAML agents)
        - Directories containing agent.py (Python agents)

        Args:
            locations: List of directories to search

        Returns:
            Dictionary mapping agent names (lowercase) to SourceResolution objects

        """
        discovered: dict[str, SourceResolution] = {}

        for location in locations:
            if not location.is_dir():
                continue

            self._discover_dsl_agents(location, discovered)
            self._discover_yaml_agents(location, discovered)
            self._discover_python_agents(location, discovered)

        logger.info(
            "Discovered %d agents in %d locations", len(discovered), len(locations),
        )
        return discovered

    def _discover_dsl_agents(
        self,
        location: Path,
        discovered: dict[str, SourceResolution],
    ) -> None:
        """Discover DSL (.sr) agents in a location.

        Args:
            location: Directory to search
            discovered: Dict to add discovered agents to (modified in place)

        """
        for sr_file in location.rglob("*.sr"):
            if self._is_excluded(sr_file):
                continue
            name = sr_file.stem.lower()
            if name not in discovered:
                self._try_add_resolution(sr_file, name, discovered, "DSL")

    def _discover_yaml_agents(
        self,
        location: Path,
        discovered: dict[str, SourceResolution],
    ) -> None:
        """Discover YAML (.yaml, .yml) agents in a location.

        Args:
            location: Directory to search
            discovered: Dict to add discovered agents to (modified in place)

        """
        for pattern in ("*.yaml", "*.yml"):
            for yaml_file in location.rglob(pattern):
                if self._is_excluded(yaml_file):
                    continue
                name = yaml_file.stem.lower()
                if name not in discovered:
                    self._try_add_resolution(yaml_file, name, discovered, "YAML")

    def _discover_python_agents(
        self,
        location: Path,
        discovered: dict[str, SourceResolution],
    ) -> None:
        """Discover Python agents (directories with agent.py) in a location.

        Args:
            location: Directory to search
            discovered: Dict to add discovered agents to (modified in place)

        """
        for agent_py in location.rglob("agent.py"):
            if self._is_excluded(agent_py):
                continue
            agent_dir = agent_py.parent
            name = agent_dir.name.lower()
            if name not in discovered:
                self._try_add_resolution(agent_dir, name, discovered, "Python")

    def _try_add_resolution(
        self,
        path: Path,
        name: str,
        discovered: dict[str, SourceResolution],
        format_label: str,
    ) -> None:
        """Try to resolve a path and add it to discovered agents.

        Args:
            path: Path to resolve (file or directory)
            name: Agent name
            discovered: Dict to add to (modified in place)
            format_label: Format label for logging

        """
        try:
            resolution = self._resolve_file(path)
            discovered[name] = resolution
            logger.debug("Discovered %s agent '%s' at %s", format_label, name, path)
        except ValueError as e:
            logger.warning("Failed to resolve %s: %s", path, e)
