"""Configure command implementation."""

import sys
import tomllib
from pathlib import Path
from abc import ABC, abstractmethod

import toml

from streetrace.args import Args


class ConfigParameter(ABC):
    """Base class for configuration parameters."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Parameter name."""
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable parameter name."""
    
    @abstractmethod
    def get_value(self, config: dict) -> str:
        """Get current value from config."""
    
    @abstractmethod
    def set_value(self, config: dict) -> None:
        """Interactive value setting."""
    
    @abstractmethod
    def clear_value(self, config: dict) -> None:
        """Clear value from config."""


class ModelParameter(ConfigParameter):
    """Model configuration parameter."""
    
    @property
    def name(self) -> str:
        return "model"
    
    @property
    def display_name(self) -> str:
        return "Model"
    
    def get_value(self, config: dict) -> str:
        return config.get("model", "Not set")
    
    def set_value(self, config: dict) -> None:
        model = input("Enter model name (e.g., anthropic/claude-3-5-sonnet-20241022): ").strip()
        if model:
            config["model"] = model
    
    def clear_value(self, config: dict) -> None:
        config.pop("model", None)


class ConfigManager:
    """Manage TOML configuration files."""
    
    def __init__(self, args: Args):
        self.args = args
        self.global_config_path = Path.home() / ".streetrace" / "config.toml"
        self.local_config_path = args.working_dir / ".streetrace" / "config.toml"
        self.parameters = [ModelParameter()]
    
    def load_config(self, is_global: bool) -> dict:
        """Load configuration from TOML file."""
        config_path = self.global_config_path if is_global else self.local_config_path
        if config_path.exists():
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        return {}
    
    def save_config(self, config: dict, is_global: bool) -> None:
        """Save configuration to TOML file."""
        config_path = self.global_config_path if is_global else self.local_config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            toml.dump(config, f)
    
    def show_config(self, is_global: bool) -> None:
        """Display current configuration."""
        scope = "Global" if is_global else "Local"
        config = self.load_config(is_global)
        print(f"{scope} configuration:")
        for param in self.parameters:
            value = param.get_value(config)
            print(f"  {param.display_name}: {value}")
    
    def reset_config(self, is_global: bool) -> None:
        """Reset configuration with confirmation."""
        scope = "global" if is_global else "local"
        confirm = input(f"Clear all settings from {scope} config? (y/N): ").strip().lower()
        if confirm == 'y':
            config_path = self.global_config_path if is_global else self.local_config_path
            if config_path.exists():
                config_path.unlink()
            print(f"{scope.capitalize()} configuration cleared.")
        else:
            print("Cancel - No changes made")
    
    def interactive_config(self, is_global: bool) -> None:
        """Interactive configuration menu."""
        scope = "Global" if is_global else "Local"
        config = self.load_config(is_global)
        
        while True:
            print(f"\n{scope} configuration menu")
            for i, param in enumerate(self.parameters, 1):
                value = param.get_value(config)
                print(f"{i}. Configure {param.display_name} (current: {value})")
            
            print(f"{len(self.parameters) + 1}. Show all settings")
            print(f"{len(self.parameters) + 2}. Clear all settings")
            print(f"{len(self.parameters) + 3}. Save & Exit")
            print(f"{len(self.parameters) + 4}. Exit without saving")
            
            choice = input(f"Select option (1-{len(self.parameters) + 4}): ").strip()
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(self.parameters):
                    self.parameters[choice_num - 1].set_value(config)
                elif choice_num == len(self.parameters) + 1:
                    print("\nCurrent Settings:")
                    for param in self.parameters:
                        value = param.get_value(config)
                        print(f"  {param.display_name}: {value}")
                elif choice_num == len(self.parameters) + 2:
                    confirm = input("Clear all settings? (y/N): ").strip().lower()
                    if confirm == 'y':
                        for param in self.parameters:
                            param.clear_value(config)
                elif choice_num == len(self.parameters) + 3:
                    self.save_config(config, is_global)
                    print(f"{scope} configuration saved")
                    break
                elif choice_num == len(self.parameters) + 4:
                    print("Exit without saving")
                    break
                else:
                    print(f"Invalid option. Please select 1-{len(self.parameters) + 4}.")
            except ValueError:
                print(f"Invalid option. Please select 1-{len(self.parameters) + 4}.")


def run_configure(args: Args) -> None:
    """Run the configure command."""
    config_manager = ConfigManager(args)
    
    # Validate argument combinations
    if args.show and not (args.global_ or args.local):
        print("Error: --show requires either --global or --local")
        show_usage()
        return
    
    if args.reset and not (args.global_ or args.local):
        print("Error: --reset requires either --global or --local")
        show_usage()
        return
    
    if args.global_ and args.local:
        print("Error: Cannot specify both --global and --local")
        show_usage()
        return
    
    if not (args.show or args.reset or args.global_ or args.local):
        show_usage()
        return
    
    # Execute based on arguments
    if args.show:
        config_manager.show_config(args.global_)
    elif args.reset:
        config_manager.reset_config(args.global_)
    elif args.global_:
        config_manager.interactive_config(True)
    elif args.local:
        config_manager.interactive_config(False)


def show_usage() -> None:
    """Show configure command usage."""
    print("Usage: streetrace configure [OPTIONS]")
    print("\nOptions:")
    print("  --show --global     Show global configuration")
    print("  --show --local      Show local configuration")
    print("  --reset --global    Reset global configuration")
    print("  --reset --local     Reset local configuration")
    print("  --global            Interactive global configuration")
    print("  --local             Interactive local configuration")