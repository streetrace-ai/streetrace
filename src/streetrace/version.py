"""Version utility for StreetRace application."""

import sys
from importlib.metadata import version


def get_streetrace_version() -> str:
    """Get the StreetRace application version.

    Returns:
        Version string or "unknown" if version cannot be determined

    """
    try:
        return version("streetrace")
    except Exception:  # noqa: BLE001
        # Broad exception handling is acceptable here as we want to gracefully
        # handle any version lookup failures (missing package, corrupted metadata, etc.)
        return "unknown"


def show_version() -> None:
    """Display the application version and exit."""
    app_version = get_streetrace_version()
    if app_version == "unknown":
        print("StreetRace🚗💨 (version unknown)")  # noqa: T201
    else:
        print(f"StreetRace🚗💨 {app_version}")  # noqa: T201
    sys.exit(0)
