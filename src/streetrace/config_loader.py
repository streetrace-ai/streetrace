"""Configuration loader for StreetRace."""

import logging
import tomllib
from pathlib import Path

from streetrace.args import Args

logger = logging.getLogger(__name__)


def load_model_from_config(args: Args) -> str | None:
    """Load model configuration with priority: CLI > local > global.

    Args:
        args: Parsed command line arguments

    Returns:
        Model name or None if not found

    """
    # Priority 1: Command line argument
    if args.model:
        return args.model

    # Priority 2: Local configuration
    local_config_path = args.working_dir / ".streetrace" / "config.toml"
    if local_config_path.exists():
        try:
            with local_config_path.open("rb") as f:
                config = tomllib.load(f)
                if "model" in config:
                    model_value = config["model"]
                    return str(model_value) if model_value is not None else None
        except (OSError, tomllib.TOMLDecodeError) as e:
            logger.debug("Failed to load local config: %s", e)

    # Priority 3: Global configuration
    global_config_path = Path.home() / ".streetrace" / "config.toml"
    if global_config_path.exists():
        try:
            with global_config_path.open("rb") as f:
                config = tomllib.load(f)
                if "model" in config:
                    model_value = config["model"]
                    return str(model_value) if model_value is not None else None
        except (OSError, tomllib.TOMLDecodeError) as e:
            logger.debug("Failed to load global config: %s", e)

    return None
