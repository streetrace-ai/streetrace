"""ADK Session Service that maintains a directory of sessions in JSON files."""

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.events import Event
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import (
        GetSessionConfig,
        ListSessionsResponse,
    )

    from streetrace.session.json_serializer import JSONSessionSerializer

from google.adk.sessions.in_memory_session_service import InMemorySessionService

from streetrace.log import get_logger

logger = get_logger(__name__)


class JSONSessionService(InMemorySessionService):
    """ADK Session Service that combines in-memory and json storage."""

    def __init__(
        self,
        serializer: "JSONSessionSerializer",
    ) -> None:
        """Initialize a new instance of JSONSessionService."""
        super().__init__()  # type: ignore[no-untyped-call]
        self.serializer = serializer

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: "GetSessionConfig | None" = None,
    ) -> "Session | None":
        """Get a session, trying memory first, then falling back to storage."""
        session = await super().get_session(
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

        if session is None:
            msg = "Session not found (this is unexpected)."
            raise ValueError(msg)

        if app_name not in self.sessions:
            self.sessions[app_name] = {}
        if user_id not in self.sessions[app_name]:
            self.sessions[app_name][user_id] = {}

        in_memory_session = copy.deepcopy(session)
        self.sessions[app_name][user_id][session_id] = in_memory_session
        return self._merge_state(
            app_name,
            user_id,
            copy.deepcopy(session),
        )

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> "Session":
        """Create a session in memory and writes it to storage."""
        session = await super().create_session(
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

    async def replace_events(
        self,
        *,
        session: "Session",
        new_events: "list[Event]",
        start_at: int = 0,
    ) -> "Session | None":
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
        new_session = await super().create_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
            state=session.state,
        )
        for i in range(start_at):
            await super().append_event(new_session, session.events[i])
        for event in new_events:
            await super().append_event(new_session, event)
        updated_session = await super().get_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
        )
        if not updated_session:
            msg = "The session has been created above, and now missing"
            raise AssertionError(msg)
        new_session = updated_session
        # TODO(krmrn42): Restore session in try..except
        #   (easier to do if we compose instead of inherit).
        if new_session is not None:
            self.serializer.write(new_session)
        return new_session

    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: str,
    ) -> "ListSessionsResponse":
        """List sessions from the storage."""
        from google.adk.sessions.base_session_service import ListSessionsResponse

        logger.debug("Listing sessions from storage for %s/%s.", app_name, user_id)
        sessions_iter = self.serializer.list_saved(app_name=app_name, user_id=user_id)
        return ListSessionsResponse(sessions=list(sessions_iter))

    async def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Delete a session from memory and storage."""
        await super().delete_session(
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

    async def append_event(
        self,
        session: "Session",
        event: "Event",
    ) -> "Event":
        """Append an event to a session in memory and update the storage."""
        evt = await super().append_event(
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
