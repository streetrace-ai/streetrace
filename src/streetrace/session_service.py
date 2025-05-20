"""ADK Session Service that maintains a directory of sessions in JSON files."""

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any, override

from google.adk.events import Event
from google.adk.sessions import InMemorySessionService, Session
from google.adk.sessions.base_session_service import (
    GetSessionConfig,
    ListSessionsResponse,
)

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
        session: Session | None = None,
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
        config: GetSessionConfig | None = None,  # noqa: ARG002
    ) -> Session | None:
        """Read a session from a JSON file.

        The config parameter is currently not used for filtering during read.
        """
        path = self._file_path(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        try:
            return Session.model_validate_json(path.read_text())
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            logger.exception("Cannot read session at %s", path)
            return None

    def write(
        self,
        session: Session,
    ) -> Path:
        """Write a session to a JSON file."""
        path = self._file_path(session=session)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(session.model_dump_json())
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
            except OSError:  # pragma: no cover
                logger.exception("Error deleting session file %s", path)
            else:
                try:
                    path.parent.rmdir()
                    path.parent.parent.rmdir()
                except OSError:  # pragma: no cover
                    pass

        elif path.is_dir():  # pragma: no cover
            msg = f"Incorrect data storage structure, '{path}' is a directory, not deleting."
            logger.error(msg)

    def list_saved(
        self,
        *,
        app_name: str,
        user_id: str,
    ) -> Iterator[Session]:
        """List saved sessions by reading their JSON files, yielding minimal sessions."""
        root_path = self.storage_path / app_name / user_id
        if not root_path.is_dir():
            return
        for path in root_path.rglob("*.json"):
            if not path.is_file():  # pragma: no cover
                continue
            try:
                session = Session.model_validate_json(path.read_text())
            except (OSError, UnicodeDecodeError):  # pragma: no cover
                logger.exception(
                    "Could not read session file %s for listing, skipping...",
                    path,
                )
                continue
            else:
                if not session:  # pragma: no cover
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


class JSONSessionService(InMemorySessionService):
    """ADK Session Service that combines in-memory and json storage."""

    def __init__(
        self,
        storage_path: Path,
        serializer: JSONSessionSerializer | None = None,
    ) -> None:
        """Initialize a new instance of JSONSessionService."""
        super().__init__()
        self.serializer = serializer or JSONSessionSerializer(storage_path=storage_path)
        logger.info(
            "JSONSessionService initialized with storage path: %s",
            storage_path.resolve(),
        )

    @override
    def get_session(  # type: ignore[incompatible override]
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        """Get a session, trying memory first, then falling back to storage."""
        # TODO(krmrn42): If app_name is not provided, use the cwd folder name
        # TODO(krmrn42): If user_id is not provided, use streetrace.utils.uid.get_user_identity
        # TODO(krmrn42): If session_id is not provided, use current time in human readable format

        session = super().get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            config=config,
        )
        if session:
            logger.debug(
                "Session %s found in memory for %s/%s.",
                session_id,
                app_name,
                user_id,
            )
            return session

        logger.debug(
            "Session %s not in memory, trying storage for %s/%s.",
            session_id,
            app_name,
            user_id,
        )
        session = self.serializer.read(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            config=config,
        )

        if session is None:
            logger.debug(
                "Session %s not found in storage for %s/%s.",
                session_id,
                app_name,
                user_id,
            )
            return None

        logger.debug(
            "Session %s loaded from storage for %s/%s.",
            session_id,
            app_name,
            user_id,
        )
        if app_name not in super().sessions:  # pragma: no cover
            super().sessions[app_name] = {}
        if user_id not in super().sessions[app_name]:  # pragma: no cover
            super().sessions[app_name][user_id] = {}

        in_memory_session = copy.deepcopy(session)
        super().sessions[app_name][user_id][session_id] = in_memory_session
        return super()._merge_state(app_name, user_id, copy.deepcopy(session))

    @override
    def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        """Create a session in memory and writes it to storage."""
        # TODO(krmrn42): Handle session_id generation (e.g. human readable time) if None
        session = super().create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
            session_id=session_id,
        )
        logger.info(
            "Session %s created for %s/%s. Writing to storage.",
            session.id,
            app_name,
            user_id,
        )
        self.serializer.write(session=session)
        return session

    @override
    def list_sessions(
        self,
        *,
        app_name: str,
        user_id: str,
    ) -> ListSessionsResponse:
        """List sessions from the storage."""
        logger.debug("Listing sessions from storage for %s/%s.", app_name, user_id)
        sessions_iter = self.serializer.list_saved(app_name=app_name, user_id=user_id)
        return ListSessionsResponse(sessions=list(sessions_iter))

    @override
    def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Delete a session from memory and storage."""
        super().delete_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(
            "Session %s deleted from memory for %s/%s. Deleting from storage.",
            session_id,
            app_name,
            user_id,
        )
        self.serializer.delete(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

    @override
    def append_event(self, session: Session, event: Event) -> Event:
        """Append an event to a session in memory and updates the storage."""
        session_in_memory = super().get_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
        )

        if not session_in_memory:  # pragma: no cover
            logger.warning(
                "Session %s for append_event not found in memory. Base class will create it.",
                session.id,
            )

        evt = super().append_event(
            session=session,
            event=event,
        )

        authoritative_session = super().sessions[session.app_name][session.user_id][
            session.id
        ]

        logger.debug(
            "Event appended to session %s. Updating storage.",
            authoritative_session.id,
        )
        self.serializer.write(session=authoritative_session)
        return evt
