"""Tool results model to help return proper messages to LLM."""

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


def op_success(tool_name: str, output: str) -> OpResult:
    """Construct OpResult message for a successful tool call."""
    return OpResult(
        tool_name=tool_name,
        result=OpResultCode.SUCCESS,
        output=output,
        error=None,
    )


def op_error(tool_name: str, error: str) -> OpResult:
    """Construct OpResult message for a failed tool call."""
    return OpResult(
        tool_name=tool_name,
        result=OpResultCode.FAILURE,
        output=None,
        error=error,
    )


def cli_success(tool_name: str, stdout: str, stderr: str) -> CliResult:
    """Construct CliResult message for a successful tool call."""
    return CliResult(
        tool_name=tool_name,
        result=OpResultCode.SUCCESS,
        stdout=stdout,
        stderr=stderr,
    )


def cli_error(tool_name: str, stdout: str, stderr: str) -> CliResult:
    """Construct CliResult message for a failed tool call."""
    return CliResult(
        tool_name=tool_name,
        result=OpResultCode.SUCCESS,
        stdout=stdout,
        stderr=stderr,
    )
