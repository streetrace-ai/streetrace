"""Configuration loader for StreetRace."""

import tomllib
from pathlib import Path

from streetrace.args import Args


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
            with open(local_config_path, "rb") as f:
                config = tomllib.load(f)
                if "model" in config:
                    return config["model"]
        except Exception:
            # Ignore config file errors and continue
            pass
    
    # Priority 3: Global configuration
    global_config_path = Path.home() / ".streetrace" / "config.toml"
    if global_config_path.exists():
        try:
            with open(global_config_path, "rb") as f:
                config = tomllib.load(f)
                if "model" in config:
                    return config["model"]
        except Exception:
            # Ignore config file errors and continue
            pass
    
    return None