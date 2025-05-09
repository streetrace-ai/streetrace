"""Testing main loops.

This is an example of wiring app most of the things we need - asyncio, ADK, MCP, litellm, rich.

Next steps:

1. A big refactoring to remove the interaction manager and replace it with ADK.
2. Refactor MCPClient to produce an ADK Agent for each server.
3. Allow defining Agents in a config.
4. How to run reflexion agent in ADK? <-- essential, as it produces long term memory.
5. Manage long term memory.

What we want to see:

- [x] Async main
- [ ] MCP tools - https://google.github.io/adk-docs/tools/mcp-tools/#using-mcp-tools-in-your-own-agent-out-of-adk-web
- [x] Custom litellm provider
- [x] Diff rendering
- [x] ADK
- [x] Print info message and status not interfering
"""

# ruff: noqa: T201, D101, D102, D103, D104, E402

import asyncio
from collections import deque
from typing import NoReturn

import litellm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from litellm import (
    ChatCompletionMessageToolCall,
    Choices,
    CustomLLM,
    Function,
    Message,
    acompletion,
)
from litellm.types.utils import ModelResponse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

_APP_NAME = "StreetRace🚗💨 v0.2"
_FAKE_MODEL = "fake/model"
_FAKE_RESPONSE = """\
    Alright, imagine if every time you went to school, there was only one kind of cookie allowed, \
    and everyone had to like that cookie. Disestablishmentarianism is a big word for people who \
    think everyone should be able to choose their favorite cookie and not be told what to like \
    by just one kind. It’s like saying everyone should have the freedom to choose their favorite \
    cookie, even if it’s different from what most people have.""".replace(
    " " * 4,
    "",
)
_RICH_INFO = "#d0d0d0"
_RICH_TOOL_OUTPUT_TEXT_STYLE = _RICH_INFO
_RICH_TOOL_OUTPUT_CODE_THEME = "monokai"


async def process_prompt_direct(model: str, prompt: str) -> str:
    completion = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    await asyncio.sleep(5)
    return completion.get("choices")[0].get("message").get("content")


async def process_prompt(_model: str, prompt: str) -> str:
    runner = Runner(
        app_name=_APP_NAME,
        session_service=session_service_stateful,
        agent=root_agent,
    )
    return await call_agent_async(prompt, runner, USER_ID_STATEFUL, SESSION_ID_STATEFUL)


# region ADK

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm


def get_weather(city: str) -> dict:
    """Retrieve the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.

    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    return {
        "status": "error",
        "error_message": f"Weather information for '{city}' is not available.",
    }


def get_current_time(city: str) -> dict:
    """Return the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.

    """
    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (f"Sorry, I don't have timezone information for {city}."),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    return {"status": "success", "report": report}


root_agent = Agent(
    name="weather_time_agent",
    model=LiteLlm(_FAKE_MODEL),
    description=("Agent to answer questions about the time and weather in a city."),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=[get_weather, get_current_time],
)

session_service_stateful = InMemorySessionService()
# Define a NEW session ID for this part of the tutorial
SESSION_ID_STATEFUL = "session_state_demo_001"
USER_ID_STATEFUL = "user_state_demo"

# Define initial state data - user prefers Celsius initially
initial_state = {
    "user_preference_temperature_unit": "Celsius",
}

# Create the session, providing the initial state
session_stateful = session_service_stateful.create_session(
    app_name=_APP_NAME,  # Use the consistent app name
    user_id=USER_ID_STATEFUL,
    session_id=SESSION_ID_STATEFUL,
    state=initial_state,  # <<< Initialize state during creation
)

from google.genai import types  # For creating message Content/Parts


# see https://google.github.io/adk-docs/tutorials/agent-team/#step-1-your-first-agent-basic-weather-lookup
async def call_agent_async(
    query: str,
    runner: Runner,
    user_id: str,
    session_id: str,
) -> str:
    """Send a query to the agent and prints the final response."""
    print(f"\n>>> User Query: {query}")

    # Prepare the user's message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response."  # Default

    # Key Concept: run_async executes the agent logic and yields Events.
    # We iterate through events to find the final answer.
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # You can uncomment the line below to see *all* events during execution
        print(
            f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}",
        )

        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif (
                event.actions and event.actions.escalate
            ):  # Handle potential errors/escalations
                final_response_text = (
                    f"Agent escalated: {event.error_message or 'No specific message.'}"
                )
            # Add more checks here if needed (e.g., specific error codes)
            break  # Stop processing events once the final response is found

    return final_response_text


# endregion

# region Custom litellm provider

FAKE_COMPLETION_MESSAGES = deque()
FAKE_COMPLETION_MESSAGES.append(
    ModelResponse(
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=Message(
                    content=_FAKE_RESPONSE,
                    role="assistant",
                ),
            ),
        ],
        model="fake-model",
        object="chat.completion",
    ),
)
FAKE_COMPLETION_MESSAGES.append(
    ModelResponse(
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=Message(
                    content=_FAKE_RESPONSE,
                    role="assistant",
                    tool_calls=[
                        ChatCompletionMessageToolCall(
                            id="call_1",
                            type="function",
                            function=Function(
                                name="get_weather",
                                arguments='{"city": "Seattle"}',
                            ),
                        ),
                    ],
                ),
            ),
        ],
        model="fake-model",
        object="chat.completion",
    ),
)
FAKE_COMPLETION_MESSAGES.append(
    ModelResponse(
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=Message(
                    content=_FAKE_RESPONSE,
                    role="assistant",
                    tool_calls=[
                        ChatCompletionMessageToolCall(
                            id="call_1",
                            type="function",
                            function=Function(
                                name="get_current_time",
                                arguments='{"city": "Seattle"}',
                            ),
                        ),
                    ],
                ),
            ),
        ],
        model="fake-model",
        object="chat.completion",
    ),
)


class FakeLLM(CustomLLM):
    async def acompletion(self, *args, **kwargs) -> ModelResponse:
        return FAKE_COMPLETION_MESSAGES.pop()


fake_llm = FakeLLM()

litellm.custom_provider_map = [
    {"provider": "fake", "custom_handler": fake_llm},
]

# endregion Custom litellm provider

# region Diff rendering


async def get_diff() -> str:
    import difflib

    initial_content = "Line 1\nLine 2\nLine 3"
    new_content = "Line 1\nLine Two\nLine 3"
    diff_lines = difflib.unified_diff(
        initial_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile="original.py",
        tofile="modified.py",
    )
    await asyncio.sleep(1)
    return "".join(diff_lines)


def print_diff(diff_str: str) -> NoReturn:
    title = "Diff Result"
    # Use Panel to frame the output
    syntax = Syntax(
        diff_str,
        "diff",
        theme=_RICH_TOOL_OUTPUT_CODE_THEME,
        line_numbers=True,
    )
    console.print(
        Panel(syntax, title=title),
        style=_RICH_TOOL_OUTPUT_TEXT_STYLE,
    )


# endregion Diff rendering

# region Print info message and status not interfering


def print_response(message: str) -> NoReturn:
    console.print(message, style=_RICH_INFO)


# endregion

# region Async main


async def main() -> None:
    response: str = None
    with console.status("Working", spinner="hamburger"):
        for _ in range(1):
            print_diff(await get_diff())
        response = await process_prompt(
            _FAKE_MODEL,
            "Explain disestablishmentarianism to a smart five year old.",
        )
        print_response(response)
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

# endregion
