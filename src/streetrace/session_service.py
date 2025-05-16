"""Implements an ADK Session Service that maintains a directory of sessions serialized as Markdown.

Key requirements:

1. Comfortable history reading
2. Start with a previous session
3. Modify history easily

Why MD? It seems the least appropriate format for data serialization. But it provides
the main advantage that I need - easy and full control. I want to be able to copy
sessions, modify them, see them nicely formatted, etc.

Potential challenges:

Models sometimes output crap. And putting their crappy markdown response in our nide and clean
markdown history file will ruin the history.

After some testing and digging, I think the best way is to re-format the markdown to guarantee
a valid document. This gives us flexibility in how we want to render it. One way to do it is
https://github.com/lepture/mistune.

Alternatives considered:

* SQLite: more reliable, but will require more work to actually dive into the messages,
    editing histories, etc.
* Open WebUI / Chatbot UI: the core value is chat with local model. Even though web-based chat is
    something I am thinking about for Streetrace, I don't see it as a core value. The main thing I
    need is an easy way of editing histories.
* FastChat / Text Generation WebUI: the main value is training / experimenting, not something I am
    looking for.

Why editing histories?

Imagine spending an hour working with a model to build something, and then it starts doing really
weird stuff. What I want is go to the history, cherry pick it, and try again, instead of `git reset`
and start over, or even worse explain where we are in a new chat.

StreetRace🚗💨 has a compact feature for the ever growing histories, and I'm thinking about an
option to auto-re-write history on every turn so the history size is sane, but it doesn't help when
the model starts outputing crap.
"""

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

class MDSessionSerializer:
    """Serialize and deserialize ADK Session to/from Markdown.

    Notes: this is not a complete serializer. It saves and reads
    only a specific subset of fields.
    """

    def __init__(self, store_path: Path) -> None:
        """Initialize a new instance of MDSessionSerializer."""
        self.store_path = store_path

    @staticmethod
    def _read_from_file(
        path: Path,
    ) -> Session | None:
        try:
            #TOOD(krmrn42): Read session from markdown file
            raise NotImplementedError
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError):
            logger.exception("Could not read session file %s", path)
            raise

    @staticmethod
    def _write_to_file(
        path: Path,
        session: Session,
    ) -> Session | None:
        #TOOD(krmrn42): Serialize the session to markdown file
        raise NotImplementedError

    def _md_path(
        self,
        *,
        app_name: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        session: Session | None = None,
    ) -> Path:
        if session:
            app_name = session.app_name
            user_id = session.user_id
            session_id = session.id
        if not app_name or not user_id or not session_id:
            msg = "Either all of app_name, user_id, session_id have to be set, or a Session object providing those values."
            raise ValueError(msg)
        return self.store_path / app_name / user_id / f"{session_id}.md"

    def read(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        path = self._md_path(app_name=app_name, user_id=user_id, session_id=session_id)
        session = MDSessionSerializer._read_from_file(path)
        #TOOD(krmrn42): Apply config filters.
        return session

    def write(
        self,
        session: Session,
    ) -> Path:
        path = self._md_path(session=session)
        MDSessionSerializer._write_to_file(path, session)
        return path

    def delete(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        path = self._md_path(app_name=app_name, user_id=user_id, session_id=session_id)
        if path.is_file():
            path.unlink()
        if path.is_dir():
            msg = f"Incorrect data store structure, '{path}' is a directory"
            raise ValueError(msg)

    def list_saved(
        self,
        *,
        app_name: str,
        user_id: str,
    ) -> Iterator[Session]:
        root_path = self.store_path / app_name / user_id
        if root_path.is_dir():
            for path in root_path.rglob("*.md"):
                # TODO(krmrn42): We only need to read the last_update_time
                #       might as well include it in the name instead of reading
                #       files here.
                try:
                    session = self._read_from_file(path)
                except (OSError, UnicodeDecodeError):
                    logger.exception("Could not read session file %s, skipping...", path)
                    continue
                else:
                    if session:
                        session.events = []
                        session.state = {}
                        yield session


class MDSessionService(InMemorySessionService):
    """ADK Session Service that combines in-memory and markdown storage."""

    def __init__(self, store_path: Path, serializer: MDSessionSerializer | None = None) -> None:
        """Initialize a new instance of MDSessionService."""
        super().__init__()
        self.serializer = serializer or MDSessionSerializer(store_path=store_path)

    #TODO(krmrn42): If app_name is not provided, use the cwd folder name
    #TODO(krmrn42): If user_id is not provided, use streetrace.utils.uid.get_user_identity
    #TODO(krmrn42): If session_id is not provided, use current time in human readable format
    @override
    def get_session( # type: ignore[incompatible override]: Wrong declaration in the base class.
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        session = super().get_session(
            app_name=app_name, user_id=user_id, session_id=session_id, config=config,
        )
        if session:
            return session

        session = self.serializer.read(app_name=app_name, user_id=user_id, session_id=session_id, config=config)

        if session is None:
            return None

        # If the session was not found in memory and was read from file, populate memory:
        if app_name not in super().sessions:
            super().sessions[app_name] = {}
        if user_id not in super().sessions[app_name]:
            super().sessions[app_name][user_id] = {}
        super().sessions[app_name][user_id][session_id] = session

        copied_session = copy.deepcopy(session)
        return super()._merge_state(app_name, user_id, copied_session)

    @override
    def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        session = super().create_session(
            app_name=app_name, user_id=user_id, state=state, session_id=session_id,
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
        sessions = self.serializer.list_saved(app_name=app_name, user_id=user_id)
        return ListSessionsResponse(sessions=list(sessions))

    @override
    def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        super().delete_session(app_name=app_name, user_id=user_id, session_id=session_id)
        self.serializer.delete(app_name=app_name, user_id=user_id, session_id=session_id)

    @override
    def append_event(self, session: Session, event: Event) -> Event:
        evt = super().append_event(session=session, event=event)
        # the event has already been added in super()
        self.serializer.write(session)
        return evt
