"""Parse and organize app args."""

from collections.abc import Callable
from pathlib import Path

import typed_argparse as tap


class Args(tap.TypedArgs):
    """App args."""

    path: Path | None = tap.arg(help="Working directory")
    model: str = tap.arg(help="Model to use, see https://docs.litellm.ai/docs/set_keys")
    prompt: str | None = tap.arg(help="Non-interactive prompt mode")
    arbitrary_prompt: list[str] | None = tap.arg(
        positional=True,
        nargs="*",
        help="Prompt to use",
    )
    verbose: bool = tap.arg(help="Enables verbose (DEBUG) logging")

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
            msg = f"Specified path '{self.path}' resolved to '{work_dir}' which is not a valid directory."
            raise ValueError(
                msg,
            )

        return work_dir


def bind_and_run(app_main: Callable[[Args], None]) -> None:
    """Parse args and run the app passing the parsed args."""
    tap.Parser(Args).bind(app_main).run()
