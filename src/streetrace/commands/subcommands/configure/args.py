"""Configure subcommand arguments."""

from pathlib import Path

import typed_argparse as tap


class ConfigureArgs(tap.TypedArgs):
    """Arguments specific to the configure subcommand."""

    path: Path | None = tap.arg(help="Working directory", default=None)
    local: bool = tap.arg(help="Configure local settings", default=False)
    global_: bool = tap.arg(help="Configure global settings", default=False)
    show: bool = tap.arg(help="Show configuration settings", default=False)
    reset: bool = tap.arg(help="Reset configuration settings", default=False)

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
            raise ValueError(msg)

        return work_dir
