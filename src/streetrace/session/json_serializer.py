"""Serialize and deserialize ADK Session to/from JSON."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from google.adk.sessions import Session

from streetrace.log import get_logger

logger = get_logger(__name__)


class JSONSessionSerializer:
    """Serialize and deserialize ADK Session to/from JSON.

    Notes: this is not a complete serializer. It saves and reads
    only a necessary subset of fields.
    """

    def __init__(self, storage_path: Path) -> None:
        """Initialize a new instance of JSONSessionSerializer."""
        self.storage_path = storage_path

    def _file_path(
        self,
        *,
        app_name: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        session: "Session | None" = None,
    ) -> Path:
        """Construct the JSON file path for a session."""
        if session:
            app_name = session.app_name
            user_id = session.user_id
            session_id = session.id
        if not app_name or not user_id or not session_id:
            msg = (
                "Either all of app_name, user_id, session_id have to be set, "
                "or a Session object providing those values."
            )
            raise ValueError(msg)
        return self.storage_path / app_name / user_id / f"{session_id}.json"

    def read(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> "Session | None":
        """Read a session from a JSON file.

        The config parameter is currently not used for filtering during read.
        """
        path = self._file_path(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if not path.is_file():
            return None
        try:
            from google.adk.sessions import Session

            return Session.model_validate_json(path.read_text())
        except (OSError, UnicodeDecodeError):
            logger.exception("Cannot read session at %s", path)
            return None

    def write(
        self,
        session: "Session",
    ) -> Path:
        """Write a session to a JSON file."""
        path = self._file_path(session=session)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            session.model_dump_json(
                indent=2,
                exclude_none=True,
            ),
        )
        return path

    def delete(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Delete a session's JSON file."""
        path = self._file_path(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                logger.exception("Error deleting session file %s", path)
            else:
                try:
                    path.parent.rmdir()
                    path.parent.parent.rmdir()
                except OSError:
                    pass

        elif path.is_dir():
            msg = f"Incorrect data storage structure, '{path}' is a directory."
            logger.error(msg)

    def list_saved(
        self,
        *,
        app_name: str,
        user_id: str,
    ) -> "Iterator[Session]":
        """List saved sessions."""
        root_path = self.storage_path / app_name / user_id
        if not root_path.is_dir():
            return
        from google.adk.sessions import Session

        for path in root_path.rglob("*.json"):
            if not path.is_file():
                continue
            try:
                session = Session.model_validate_json(path.read_text())
            except (OSError, UnicodeDecodeError):
                logger.exception(
                    "Could not read session file %s for listing, skipping...",
                    path,
                )
                continue
            else:
                if not session:
                    logger.warning(
                        "Failed to read/parse session file %s for listing, skipping.",
                        path,
                    )
                    continue
                yield Session(
                    id=session.id,
                    app_name=session.app_name,
                    user_id=session.user_id,
                    last_update_time=session.last_update_time,
                    events=[],
                    state={},
                )
