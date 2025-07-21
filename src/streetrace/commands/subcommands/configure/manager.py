"""Configuration management functionality."""

import sys
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path

import toml

from .args import ConfigureArgs


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
    def get_value(self, config: dict[str, str]) -> str:
        """Get current value from config."""

    @abstractmethod
    def set_value(self, config: dict[str, str]) -> None:
        """Interactive value setting."""

    @abstractmethod
    def clear_value(self, config: dict[str, str]) -> None:
        """Clear value from config."""


class ModelParameter(ConfigParameter):
    """Model configuration parameter."""

    @property
    def name(self) -> str:
        """Parameter name."""
        return "model"

    @property
    def display_name(self) -> str:
        """Human-readable parameter name."""
        return "Model"

    def get_value(self, config: dict[str, str]) -> str:
        """Get current value from config."""
        return config.get("model", "Not set")

    def set_value(self, config: dict[str, str]) -> None:
        """Interactive value setting."""
        model = input(
            "Enter model name (e.g., anthropic/claude-3-5-sonnet-20241022): ",
        ).strip()
        if model:
            config["model"] = model

    def clear_value(self, config: dict[str, str]) -> None:
        """Clear value from config."""
        config.pop("model", None)


class ConfigManager:
    """Manage TOML configuration files."""

    def __init__(self, args: ConfigureArgs) -> None:
        """Initialize the configuration manager.

        Args:
            args: Configure command arguments.

        """
        self.args = args
        self.global_config_path = Path.home() / ".streetrace" / "config.toml"
        self.local_config_path = args.working_dir / ".streetrace" / "config.toml"
        self.parameters = [ModelParameter()]

    def load_config(self, *, is_global: bool) -> dict[str, str]:
        """Load configuration from TOML file."""
        config_path = self.global_config_path if is_global else self.local_config_path
        if config_path.exists():
            with config_path.open("rb") as f:
                loaded_config = tomllib.load(f)
                # Convert to dict[str, str] for type safety
                return {k: str(v) for k, v in loaded_config.items()}
        return {}

    def save_config(self, config: dict[str, str], *, is_global: bool) -> None:
        """Save configuration to TOML file."""
        config_path = self.global_config_path if is_global else self.local_config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w") as f:
            toml.dump(config, f)

    def show_config(self, *, is_global: bool) -> None:
        """Display current configuration."""
        scope = "Global" if is_global else "Local"
        config = self.load_config(is_global=is_global)
        sys.stdout.write(f"{scope} configuration:\n")
        for param in self.parameters:
            value = param.get_value(config)
            sys.stdout.write(f"  {param.display_name}: {value}\n")

    def reset_config(self, *, is_global: bool) -> None:
        """Reset configuration with confirmation."""
        scope = "global" if is_global else "local"
        confirm = (
            input(
                f"Clear all settings from {scope} config? (y/N): ",
            )
            .strip()
            .lower()
        )
        if confirm == "y":
            config_path = (
                self.global_config_path if is_global else self.local_config_path
            )
            if config_path.exists():
                config_path.unlink()
            sys.stdout.write(f"{scope.capitalize()} configuration cleared.\n")
        else:
            sys.stdout.write("Cancel - No changes made\n")

    def interactive_config(self, *, is_global: bool) -> None:
        """Interactive configuration menu."""
        scope = "Global" if is_global else "Local"
        config = self.load_config(is_global=is_global)
        max_options = len(self.parameters) + 4

        while True:
            self._show_menu(scope)
            choice = input(f"Select option (1-{max_options}): ").strip()

            try:
                choice_num = int(choice)
                should_exit = self._handle_menu_choice(
                    choice_num,
                    config,
                    scope,
                    is_global=is_global,
                    max_options=max_options,
                )
                if should_exit:
                    break
            except ValueError:
                self._show_invalid_option_message(max_options)

    def _show_menu(self, scope: str) -> None:
        """Show the interactive configuration menu."""
        sys.stdout.write(f"\n{scope} configuration menu\n")
        for i, param in enumerate(self.parameters, 1):
            value = param.get_value(self.load_config(is_global=scope == "Global"))
            display_text = f"{i}. Configure {param.display_name} (current: {value})\n"
            sys.stdout.write(display_text)

        sys.stdout.write(f"{len(self.parameters) + 1}. Show all settings\n")
        sys.stdout.write(f"{len(self.parameters) + 2}. Clear all settings\n")
        sys.stdout.write(f"{len(self.parameters) + 3}. Save & Exit\n")
        sys.stdout.write(f"{len(self.parameters) + 4}. Exit without saving\n")

    def _handle_menu_choice(
        self,
        choice_num: int,
        config: dict[str, str],
        scope: str,
        *,
        is_global: bool,
        max_options: int,
    ) -> bool:
        """Handle menu choice and return True if should exit."""
        if 1 <= choice_num <= len(self.parameters):
            self.parameters[choice_num - 1].set_value(config)
        elif choice_num == len(self.parameters) + 1:
            self._show_current_settings(config)
        elif choice_num == len(self.parameters) + 2:
            self._clear_all_settings(config)
        elif choice_num == len(self.parameters) + 3:
            self.save_config(config, is_global=is_global)
            sys.stdout.write(f"{scope} configuration saved\n")
            return True
        elif choice_num == len(self.parameters) + 4:
            sys.stdout.write("Exit without saving\n")
            return True
        else:
            self._show_invalid_option_message(max_options)
        return False

    def _show_current_settings(self, config: dict[str, str]) -> None:
        """Show current configuration settings."""
        sys.stdout.write("\nCurrent Settings:\n")
        for param in self.parameters:
            value = param.get_value(config)
            sys.stdout.write(f"  {param.display_name}: {value}\n")

    def _clear_all_settings(self, config: dict[str, str]) -> None:
        """Clear all configuration settings with confirmation."""
        confirm = input("Clear all settings? (y/N): ").strip().lower()
        if confirm == "y":
            for param in self.parameters:
                param.clear_value(config)

    def _show_invalid_option_message(self, max_options: int) -> None:
        """Show invalid option message."""
        sys.stdout.write(f"Invalid option. Please select 1-{max_options}.\n")


def show_usage() -> None:
    """Show configure command usage."""
    sys.stdout.write("Usage: streetrace configure [OPTIONS]\n")
    sys.stdout.write("\nOptions:\n")
    sys.stdout.write("  --show --global     Show global configuration\n")
    sys.stdout.write("  --show --local      Show local configuration\n")
    sys.stdout.write("  --reset --global    Reset global configuration\n")
    sys.stdout.write("  --reset --local     Reset local configuration\n")
    sys.stdout.write("  --global            Interactive global configuration\n")
    sys.stdout.write("  --local             Interactive local configuration\n")
