"""Experimental module that can render a full session to markdown."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types
from marko import Markdown
from marko.md_renderer import MarkdownRenderer

# Constant for magic number identified by ruff
EXPECTED_TIMESTAMP_SPLIT_PARTS = 2
TIMESTAMP_FORMAT = "%a %b %d %H:%M:%S %Y %z"
"""E.g., Thu May 15 17:46:43 2025 +0000.

Note: %Z is deprecated, but using %z is not user friendly in this context."""


_SAFE_MD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^# @"), "# [edited] @"),
    (re.compile(r"^### @"), "### [edited] @"),
    (re.compile(r"^## Conversation"), "## [edited] Conversation"),
    (re.compile(r"^## State"), "## [edited] State"),
    (re.compile(r"^## All events"), "## [edited] All events"),
    (re.compile(r"^#### call: `"), "#### [edited] call: `"),
    (re.compile(r"^#### response: `"), "#### [edited] response: `"),
]
"""Set of rules that will be replaced in the messages to allow serialization."""


class UnexpectedSessionDataError(Exception):
    """Any unextected condition seen in the session document."""

    def __init__(self, note: str, session: Session, arg: str) -> None:
        """Session and any other str to allow debugging."""
        self._note = note
        self._session = session
        self._arg = arg


class MDSessionWriter:
    """Markdown Session writer implementation."""

    def __init__(self, path: Path) -> None:
        """Initialize a new instance of MDSessionWriter writing to the provided path."""
        self.path = path
        self.md = Markdown(renderer=MarkdownRenderer)

    def __enter__(self) -> "MDSessionWriter":  # noqa: D105
        self.writer = self.path.open(mode="w", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close writer on context exit."""
        self.writer.close()

    def _write_line(self, md_line: str) -> None:
        self.writer.write(md_line)
        self.writer.write("\n")

    def _format_timestamp(self, ts: float) -> str:
        """Format a Unix timestamp into a human-readable string."""
        return datetime.fromtimestamp(ts, tz=UTC).strftime(TIMESTAMP_FORMAT)

    def _get_event_author_name(self, event: Event) -> str:
        author = event.author
        if author == "user":
            author = self._session.user_id
        return str(author)

    def _write_session_header(self) -> None:
        title_template = "# @{user_name} - @{model_name}\n"
        self._write_line(
            title_template.format(
                user_name=self._session.user_id,
                model_name=self._session.app_name,
            ),
        )

        metadata_template = "Last updated: {datestr}\n"
        session_ts_str = self._format_timestamp(self._session.last_update_time)
        self._write_line(
            metadata_template.format(
                datestr=session_ts_str,
            ),
        )

    def _safe_md(self, md: str) -> str:
        """Fix md syntax and replace common format markers in the input text."""
        md_lines = self.md.render(self.md.parse(md)).splitlines(keepends=True)
        md_buffer: list[str] = []
        for line in md_lines:
            new_line = line
            for pattern, replacement in _SAFE_MD_RULES:
                if pattern.search(line):
                    new_line = pattern.sub(replacement, line)
            md_buffer.append(new_line)

        return "".join(md_buffer)

    def _write_session_conversation(self) -> None:
        self._write_line("## Conversation\n")
        lines_written = 0
        if not self._session.events:
            self._write_line("No final responses recorded.")
            return
        for event in self._session.events:
            if (
                not event.is_final_response()
                or not event.content
                or not event.content.parts
            ):
                continue
            message_template = "### _{author}_\n\n_{datestr}_\n"
            author = self._get_event_author_name(event)
            datestr = self._format_timestamp(event.timestamp)
            self._write_line(
                message_template.format(
                    author=author,
                    datestr=datestr,
                ),
            )
            for part in event.content.parts:
                err_msg = None
                if part.text:
                    safe_md = self._safe_md(part.text)
                    self._write_line(safe_md)
                    lines_written += 1
                else:
                    err_msg = "text not in final response"
                if part.function_call or part.function_response:
                    err_msg = "function_call or function_response in final response"
                if err_msg:
                    raise UnexpectedSessionDataError(
                        str(err_msg),
                        self._session,
                        part.model_dump_json(),
                    )
        if lines_written == 0:
            self._write_line("No final responses recorded.")

    def _write_session_state(self) -> None:
        if not self._session.state:
            return
        self._write_line("## State\n")
        state_list_item_template = "* `{item_key}`: {item_value}"
        for key, value in self._session.state.items():
            value_str = json.dumps(value, indent=2)
            if len(value_str.splitlines()) > 1:
                padding = " " * 2
                padded_lines = "".join(
                    [padding + line for line in value_str.splitlines(keepends=True)],
                )
                value_str = f"\n{padding}```json\n{padded_lines}\n{padding}```\n"
            self._write_line(
                state_list_item_template.format(
                    item_key=key,
                    item_value=value_str,
                ),
            )

    def _write_tool(self, message_type: str, tool_name: str, data_json: str) -> None:
        padding = " " * 4
        template = str(
            "#### {message_type}: `{tool_name}`\n"
            "\n"
            "{padding}```json\n"
            "{data_json}\n"
            "{padding}```\n",
        )
        data_json_padded = "".join(
            [padding + line for line in data_json.splitlines(keepends=True)],
        )
        md = template.format(
            message_type=message_type,
            tool_name=tool_name,
            padding=padding,
            data_json=data_json_padded,
        )
        self._write_line(md)

    def _write_part(self, part: genai_types.Part) -> tuple[bool, str]:
        err_msg = ""
        part_written = False
        if part.text:
            safe_md = self._safe_md(part.text)
            quoted = "".join(
                ["> " + line for line in safe_md.splitlines(keepends=True)],
            )
            if quoted[-1] != "\n":
                quoted += "\n"
            self._write_line(quoted)
            part_written = True

        if part.function_call:
            data = part.function_call.model_dump_json(
                indent=2,
                exclude_none=True,
            )
            if part.function_call.name:
                self._write_tool("call", part.function_call.name, data)
                part_written = True
            else:
                err_msg = "function_call.name is required"

        if part.function_response:
            data = part.function_response.model_dump_json(
                indent=2,
                exclude_none=True,
            )
            if part.function_response.name:
                self._write_tool(
                    "response",
                    part.function_response.name,
                    data,
                )
                part_written = True
            else:
                err_msg = "function_response.name is required"

        return part_written, err_msg

    def _write_session_events(self) -> None:
        self._write_line("## All events\n")
        if not self._session.events:
            self._write_line("No events recorded.")
            return
        parts_written = 0
        previous_event_author = None
        for event in self._session.events:
            author = self._get_event_author_name(event)

            if previous_event_author != author:
                author_header_template = "### _{author}_\n"
                self._write_line(
                    author_header_template.format(
                        author=author,
                    ),
                )
                previous_event_author = author

            if event.content and event.content.parts:
                for part in event.content.parts:
                    part_written, err_msg = self._write_part(part)
                    if part_written:
                        parts_written += 1
                    if err_msg:
                        raise UnexpectedSessionDataError(
                            err_msg,
                            self._session,
                            part.model_dump_json(),
                        )
        if parts_written == 0:
            self._write_line("No events recorded.")

    def _write_session_end(self) -> None:
        self._write_line("---")

    def write_session(self, session: Session) -> None:
        """Serialize the session to a markdown file using Marko AST construction."""
        self._session = session
        self._write_session_header()
        self._write_session_conversation()
        self._write_session_state()
        self._write_session_events()
        self._write_session_end()
