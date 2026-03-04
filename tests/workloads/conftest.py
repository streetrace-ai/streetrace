"""Shared fixtures for workloads tests."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from streetrace.system_context import SystemContext
from streetrace.ui.ui_bus import UiBus


@pytest.fixture
def mock_ui_bus() -> UiBus:
    """Create a mock UiBus."""
    return Mock(spec=UiBus)


@pytest.fixture
def context_dir(tmp_path: Path) -> Path:
    """Create a context directory."""
    return tmp_path / "context"


@pytest.fixture
def mock_system_context(context_dir: Path, mock_ui_bus: UiBus) -> SystemContext:
    """Create a mock SystemContext."""
    system_context = Mock(spec=SystemContext)
    system_context.ui_bus = mock_ui_bus
    system_context.config_dir = context_dir
    return system_context
