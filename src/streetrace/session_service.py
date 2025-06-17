"""ADK Session Service that maintains a directory of sessions in JSON files."""

import copy
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, override

from google.adk.events import Event
from google.adk.sessions import InMemorySessionService, Session
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
from streetrace.prompt_processor import ProcessedPrompt
from streetrace.system_context import SystemContext
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
        if not path.is_file():
            return None
        try:
            return Session.model_validate_json(path.read_text())
        except (OSError, UnicodeDecodeError):
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
    ) -> Iterator[Session]:
        """List saved sessions."""
        root_path = self.storage_path / app_name / user_id
        if not root_path.is_dir():
            return
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


# TODO(krmrn42): composition instead of inheritance
class JSONSessionService(InMemorySessionService):  # type: ignore[misc]
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
    def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        """Get a session, trying memory first, then falling back to storage."""
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
            return self.validate(session)

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

        session = self.validate(session)

        if app_name not in self.sessions:
            self.sessions[app_name] = {}
        if user_id not in self.sessions[app_name]:
            self.sessions[app_name][user_id] = {}

        in_memory_session = copy.deepcopy(session)
        self.sessions[app_name][user_id][session_id] = in_memory_session
        return self._merge_state(app_name, user_id, copy.deepcopy(session))

    def validate(self, session: Session) -> Session:
        """Validate session fixing issues that are known to cause LLM call failure.

        Currently:
        - Remove function calls that don't have matching function responses.
        - Remove function responses that don't have matching function calls.
        """
        new_events: list[Event] = []
        tool_call_event: Event | None = None
        errors_found = 0

        for event in session.events:
            if not event.content or not event.content.parts:
                new_events.append(event)
                continue

            # Check for function responses
            tool_result = [
                part for part in event.content.parts if part.function_response
            ]

            # Check for function calls
            tool_call = [part for part in event.content.parts if part.function_call]

            if tool_result:
                # This event has a function response
                if tool_call_event:
                    # We have a pending function call - this is a valid pair
                    new_events.append(tool_call_event)
                    new_events.append(event)
                    tool_call_event = None
                    errors_found -= 1
                else:
                    # Orphaned function response - skip it
                    errors_found += 1
            elif tool_call:
                # This event has a function call
                if tool_call_event:
                    # We have a previous orphaned function call - skip it
                    errors_found += 1
                tool_call_event = event
                errors_found += 1
            else:
                # Regular event (no function call or response)
                if tool_call_event:
                    # We have an orphaned function call - skip it
                    errors_found += 1
                    tool_call_event = None
                new_events.append(event)

        # If we end with an orphaned function call, it's already counted in errors_found

        if errors_found == 0:
            return session

        return self.replace_events(
            session=session,
            new_events=new_events,
        )

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

    def replace_events(
        self,
        *,
        session: Session,
        new_events: list[Event],
        start_at: int = 0,
    ) -> Session:
        """Replace events in this session starting at `start_at`.

        Create a new session overwriting the existing session. The new session contains
        events 0..start_at from the original session + the new events.

        Args:
            session: The session to replace events in.
            new_events: The new events to put to the session.
            start_at: Index in the session starting from which to write the new events.

        Returns:
            The new session object.

        """
        new_session = super().create_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
            state=session.state,
        )
        for i in range(start_at):
            super().append_event(new_session, session.events[i])
        for event in new_events:
            super().append_event(new_session, event)
        new_session = super().get_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
        )
        # TODO(krmrn42): Restore session in try..except
        #   (easier to do if we compose instead of inherit).
        self.serializer.write(new_session)
        return new_session

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
    def append_event(
        self,
        session: Session,
        event: Event,
    ) -> Event:
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


class SessionManager:
    """Manages conversation sessions."""

    current_session: Session | None = None

    def __init__(
        self,
        args: Args,
        session_service: JSONSessionService,
        system_context: SystemContext,
        ui_bus: UiBus,
    ) -> None:
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
        return self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.current_session_id,
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
                    parts=[
                        genai_types.Part.from_text(text=context_part)
                        for context_part in context
                    ],
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
        """Replace events in the current session re-creating context events."""
        session_id = self.current_session_id
        current_session = self.session_service.get_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=session_id,
        )
        if not current_session:
            msg = "Current session is missing."
            raise ValueError(msg)

        self.session_service.replace_events(
            session=current_session,
            new_events=new_events,
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

    def _squash_turn_events(
        self,
        session: Session,
    ) -> str:
        """Keep only final messages in the session.

        Perhaps we can do Recursively Summarizing as discussed in
        https://arxiv.org/abs/2308.15022 or similar here.

        Persists the modified session in store.

        Any type of conversation history tampering is experimental, so we'll need to
        figure out what works and what doesn't.

        Args:
            session: The current session.

        """
        # squash will keep only final events in the history
        # the easiest way to do that resolvign all issues is to rewrite entire history
        # because event events in the previous turns can be non-final here if
        # the user interrupted the process (Ctrl+C), e.g. multiple times.
        keep_events: list[Event] = [
            event
            for event in session.events
            if event.is_final_response() and event.content and event.content.parts
        ]
        assistant_final_response = ""
        last_event = keep_events[-1]
        if (
            last_event.author != "user"
            and last_event.content
            and last_event.content.parts
        ):
            assistant_final_response = "".join(
                [part.text for part in last_event.content.parts if part.text],
            )
        self.session_service.replace_events(
            session=session,
            new_events=keep_events,
        )
        return assistant_final_response

    def _add_project_context(
        self,
        processed_prompt: ProcessedPrompt | None,
        assistant_response: str,
        session: Session,
    ) -> None:
        """Store last user's request and assistant's response in project context.

        Experimental.
        """
        user_prompt = ""
        if processed_prompt and processed_prompt.prompt:
            user_prompt = processed_prompt.prompt
        else:
            user_prompt_parts = []
            for event in session.events:
                if event.author != "user":
                    continue
                if event.content is None or not event.content.parts:
                    continue
                text_parts = [part.text for part in event.content.parts if part.text]
                if text_parts:
                    user_prompt_parts.extend(text_parts)
            user_prompt = "\n".join(user_prompt_parts)
        self.system_context.add_context_from_turn(
            user_prompt,
            assistant_response,
        )

    def post_process(
        self,
        processed_prompt: ProcessedPrompt | None,
        original_session: Session,
    ) -> None:
        """Process session after ReAct loop.

        At the moment:

        * Squash the last turn by keeping only the user's request and assistant's
            response in session.
        * Update project context based on this turn.

        Args:
            processed_prompt: The input to the last agent interaction
            original_session: The original session.

        """
        # TODO(krmrn42): Somewhere in this process we lose user's message
        session = self.session_service.get_session(
            app_name=original_session.app_name,
            user_id=original_session.user_id,
            session_id=original_session.id,
        )
        if not session:
            msg = "Session not found."
            raise ValueError(msg)

        assistant_response = self._squash_turn_events(session)

        self._add_project_context(
            processed_prompt=processed_prompt,
            assistant_response=assistant_response,
            session=session,
        )
