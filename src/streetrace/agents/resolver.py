"""Source identifier resolution supporting names, paths, and HTTP URLs.

This module provides format-agnostic resolution of identifiers to raw content.
It can be used for YAML, Markdown, or any other text-based agent definitions.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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

    """

    content: str
    source: str
    source_type: SourceType
    file_path: Path | None = None
    content_type: str | None = None


class SourceResolver:
    """Resolves identifiers to raw content (format-agnostic).

    Supports:
    - Discovered source names (from discovery, mapped to paths)
    - File system paths (absolute, ~/, relative)
    - HTTP/HTTPS URLs with optional authentication
    """

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

        Args:
            url: HTTP(S) URL to fetch
            accept_types: MIME types to accept (default: text/plain, text/yaml)

        Returns:
            SourceResolution with fetched content

        Raises:
            ValueError: If HTTP request fails

        """
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
            logger.info("Fetched content from HTTP URL: %s", url)
            return SourceResolution(
                content=content,
                source=url,
                source_type=SourceType.HTTP_URL,
                file_path=None,
                content_type=content_type,
            )
        except httpx.HTTPError as e:
            msg = f"Failed to fetch content from {url}: {e}"
            raise ValueError(msg) from e

    def _resolve_file(self, file_path: Path) -> SourceResolution:
        """Read content from file.

        Args:
            file_path: Path to file

        Returns:
            SourceResolution with file content

        Raises:
            ValueError: If file cannot be read

        """
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Loaded content from file: %s", file_path)
            return SourceResolution(
                content=content,
                source=str(file_path),
                source_type=SourceType.FILE_PATH,
                file_path=file_path,
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
