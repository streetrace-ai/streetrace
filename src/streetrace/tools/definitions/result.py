
from enum import Enum
from typing import TypedDict


class OpResultCode(str, Enum):
    """Success or Failure to be sent to LLM as tool result."""

    SUCCESS = "success"
    FAILURE = "failure"

class BaseResult(TypedDict):
    """Result object to send to LLM."""

    tool_name: str
    result: OpResultCode

class CliResult(BaseResult):
    """CLI command result to send to LLM."""

    stdout: str | None
    stderr: str | None

class OpResult(BaseResult):
    """Tool result to send to LLM."""

    output: str | None
    error: str | None
