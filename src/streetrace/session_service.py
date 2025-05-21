"""ADK Session Service that maintains a directory of sessions in JSON files."""

import copy
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, override

from google.adk.events import Event
from google.adk.sessions import BaseSessionService, InMemorySessionService, Session
from google.adk.sessions.base_session_service import (
    GetSessionConfig,
    ListSessionsResponse,
)
from google.genai import types as genai_types
from pydantic import BaseModel
from rich.console import Console
from tzlocal import get_localzone  # For creating message Content/Parts

from streetrace.args import Args
from streetrace.log import get_logger
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.colors import Styles
from streetrace.ui.render_protocol import register_renderer
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)

_SESSION_ID_TIME_FORMAT = "%Y-%m-%d_%H-%M"


def _session_id(user_provided_id: str | None = None) -> str:
    return user_provided_id or datetime.now(tz=get_localzone()).strftime(
        _SESSION_ID_TIME_FORMAT,
    )


class DisplaySessionsList(BaseModel):
    """Internal container that holds data solely to render a list of sessions."""

    app_name: str
    user_id: str
    list_sessions: ListSessionsResponse


class SessionManager:
    """Manages conversation sessions."""

    current_session: Session | None = None

    def __init__(
        self,
        args: Args,
        session_service: BaseSessionService,
        system_context: SystemContext,
        ui_bus: UiBus,
    ):
        """Initialize a new instance of SessionManager."""
        self.session_service = session_service
        self.args = args
        self.system_context = system_context
        self.ui_bus = ui_bus
        self.current_session_id = _session_id(self.args.session_id)

    @property
    def app_name(self) -> str:
        """Get the current app name used for session ID."""
        return self.args.effective_app_name

    @property
    def user_id(self) -> str:
        """Get the current app name used for session ID."""
        return self.args.effective_user_id

    def reset_session(self, new_id: str | None = None) -> None:
        """Reset session id so the new ID will be treated as the current session id.

        This causes the SessionService to create/retrieve self.current_session_id using.
        In a normal flow, the ID should be generated automatically (leave blank), so a
        new session is created.

        get_or_create_session will always use the self.current_session_id as the current
        session id, and will create a new session if the ID does not correspond to an
        existing session.

        Args:
            new_id (Optional): Don't set in a normal scenario. This should be generated
                automatically.

        """
        self.current_session_id = _session_id(new_id)

    def get_current_session(self) -> Session | None:
        """Create the ADK agent session with empty state or get existing session."""
        session_id = self.current_session_id
        return self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=session_id,
        )

    def get_or_create_session(self) -> Session:
        """Create the ADK agent session with empty state or get existing session."""
        session_id = self.current_session_id
        session = self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=session_id,
        )
        if not session:
            session = self.session_service.create_session(
                app_name=self.app_name,
                user_id=self.user_id,
                session_id=session_id,
                state={},  # Initialize state during creation
            )
            context = self.system_context.get_project_context()
            context_event = Event(
                author="user",
                content=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text="\n".join(context))],
                ),
            )
            self.session_service.append_event(session, context_event)
            session = self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.user_id,
                session_id=session_id,
            )
            if session is None:
                msg = "session is None"
                raise AssertionError(msg)

        self.current_session = session
        return session

    def replace_current_session_events(self, new_events: list[Event]) -> None:
        session_id = self.current_session_id
        current_session = self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=session_id,
        )
        if not current_session:
            msg = "Current session is missing."
            raise ValueError(msg)

        context = self.system_context.get_project_context()
        context_event = Event(
            author="user",
            content=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text="\n".join(context))],
            ),
        )

        # Create a new history with just the summary
        new_session = self.session_service.create_session(
            app_name=current_session.app_name,
            user_id=current_session.user_id,
            state=current_session.state,
            session_id=current_session.id,
        )
        # At this point the old current session is gone from session service
        # so we are fragile. Anything goes wrong, the session is lost.

        try:
            self.session_service.append_event(new_session, context_event)
            for new_event in new_events:
                self.session_service.append_event(new_session, new_event)
        except Exception:
            msg = (
                "Failed to store compacted session, grab the message above and "
                "start over. Sorry!",
            )
            logger.exception(msg)
            self.ui_bus.dispatch_ui_update(
                ui_events.Error(msg),
            )

    def display_sessions(self) -> None:
        """List all available sessions for the current user and app."""
        sessions_response = self.session_service.list_sessions(
            app_name=self.app_name,
            user_id=self.user_id,
        )

        display_list = DisplaySessionsList(
            app_name=self.app_name,
            user_id=self.user_id,
            list_sessions=sessions_response,
        )

        self.ui_bus.dispatch_ui_update(display_list)


@register_renderer
def render_list_of_sessions(obj: DisplaySessionsList, console: Console) -> None:
    """Display a list of sessions in the console."""
    if not obj.list_sessions or not obj.list_sessions.sessions:
        msg = f"No sessions found for app '{obj.app_name}' and user '{obj.user_id}'"
        console.print(msg, Styles.RICH_INFO)
        return

    session_list = [
        f"- {session.id} (last updated: {session.last_update_time})"
        for session in obj.list_sessions.sessions
    ]

    session_listing = (
        f"Available sessions for app '{obj.app_name}' and user '{obj.user_id}':\n"
        + "\n".join(session_list)
    )

    console.print(session_listing)


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
        path.write_text(
            session.model_dump_json(
                indent=2,
                # exclude_unset=True,  # noqa: ERA001 reminder: idk, this removes events
                # exclude_defaults=True,  # noqa: ERA001 reminder: defaults are helpful
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

        if app_name not in self.sessions:  # pragma: no cover
            self.sessions[app_name] = {}
        if user_id not in self.sessions[app_name]:  # pragma: no cover
            self.sessions[app_name][user_id] = {}

        in_memory_session = copy.deepcopy(session)
        self.sessions[app_name][user_id][session_id] = in_memory_session
        return self._merge_state(app_name, user_id, copy.deepcopy(session))

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
        self.serializer.delete(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(
            "Session %s deleted for %s/%s.",
            session_id,
            app_name,
            user_id,
        )

    @override
    def append_event(self, session: Session, event: Event) -> Event:
        """Append an event to a session in memory and updates the storage."""
        evt = super().append_event(
            session=session,
            event=event,
        )

        # it's unclear how to handle if the session is missing in memory or in
        # storage, so we defer the in-memory handling to super(), and always save
        self.serializer.write(session)

        logger.debug(
            "Event appended to session %s. Updating storage.",
            session.id,
        )
        return evt
