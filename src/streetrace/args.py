"""Parse and organize app args."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typed_argparse as tap
from tzlocal import get_localzone

from streetrace.utils.uid import get_user_identity

if TYPE_CHECKING:
    from collections.abc import Callable

    from streetrace.commands.subcommands import SubcommandRegistry

_START_TIME = datetime.now(tz=get_localzone())


class Args(tap.TypedArgs):
    """App args."""

    path: Path | None = tap.arg(help="Working directory", default=None)
    model: str | None = tap.arg(
        help=(
            "Model to use, see https://docs.litellm.ai/docs/set_keys. "
            "Required if running a prompt."
        ),
    )
    command: str | None = tap.arg(
        positional=True,
        nargs="?",
        help="Command to run (configure) or prompt text",
    )
    prompt: str | None = tap.arg(help="Non-interactive prompt mode", default=None)
    arbitrary_prompt: list[str] = tap.arg(
        positional=True,
        nargs="*",
        help="Additional prompt arguments",
        default=[],
    )
    verbose: bool = tap.arg(help="Enables verbose (DEBUG) logging", default=False)
    app_name: str | None = tap.arg(
        help="Application name for the session",
        default=None,
    )
    user_id: str | None = tap.arg(help="User ID for the session", default=None)
    session_id: str | None = tap.arg(help="Session ID to use (or create)", default=None)
    list_sessions: bool = tap.arg(help="List available sessions", default=False)
    version: bool = tap.arg(help="Show version and exit", default=False)

    def is_subcommand_invocation(
        self,
        registry: SubcommandRegistry | None = None,
    ) -> bool:
        """Check if this is a subcommand invocation.

        Args:
            registry: Optional subcommand registry to use for checking.

        Returns:
            True if the command is a registered subcommand, False otherwise.

        """
        if not self.command:
            return False

        if registry is None:
            # Import here to avoid circular imports
            from streetrace.commands.subcommands import (  # noqa: PLC0415
                SubcommandRegistry,
            )

            registry = SubcommandRegistry.instance()

        return self.command in registry.list_subcommands()

    @property
    def non_interactive_prompt(self) -> tuple[str | None, bool]:
        """Get non-interactive prompt provided in arguments.

        If --prompt argument was provided, returns that.

        If there were positional arguments, returns them as a prompt.

        Returns:
            tuple[str | None, bool]:
                str | None: prompt, or None
                bool: If the prompt was provided as positional arguments

        """
        if self.prompt:
            return self.prompt, False
        if self.command and not self.is_subcommand_invocation():
            # First positional arg is treated as prompt if not a subcommand
            prompt_parts = [self.command]
            if self.arbitrary_prompt:
                prompt_parts.extend(self.arbitrary_prompt)
            return " ".join(prompt_parts), True
        if self.arbitrary_prompt:
            return " ".join(self.arbitrary_prompt), True
        return None, False

    @property
    def working_dir(self) -> Path:
        """Get working directory."""
        if self.path:
            work_dir = self.path
            if not work_dir.is_absolute():
                work_dir = Path.cwd().joinpath(work_dir).resolve()
        else:
            work_dir = Path.cwd().resolve()

        if not work_dir.is_dir():
            msg = (
                f"Specified path '{self.path}' resolved to '{work_dir}' which is "
                "not a valid directory."
            )
            raise ValueError(
                msg,
            )

        return work_dir

    @property
    def effective_app_name(self) -> str:
        """Get the application name to use for sessions.

        If app_name is provided by the user, use that.
        Otherwise, use the current working directory name.

        Returns:
            str: The application name to use for sessions

        """
        if self.app_name:
            return self.app_name
        return self.working_dir.name

    @property
    def effective_user_id(self) -> str:
        """Get the user ID to use for sessions.

        If user_id is provided by the user, use that.
        Otherwise, determine it from the environment.

        Returns:
            str: The user ID to use for sessions

        """
        if self.user_id:
            return self.user_id
        return get_user_identity()


def bind_and_run(app_main: Callable[[Args], None]) -> None:
    """Parse args and run the app passing the parsed args."""
    tap.Parser(Args).bind(app_main).run()
