# OpenAI Converter

The OpenAI converter is responsible for translating between StreetRace's common message format and OpenAI's API-specific format. This allows the rest of the application to use a consistent interface regardless of which AI provider is being used.

## Core Components

### ChoiceDeltaWrapper

A wrapper class for OpenAI's `ChoiceDelta` objects that implements the `ChunkWrapper` interface. This provides a consistent way to access content from OpenAI's streaming responses, including:

- Text content via `get_text()`
- Tool/function calls via `get_tool_calls()`

### OpenAIConverter

The main converter class that implements the `HistoryConverter` interface for OpenAI-specific types. This class centralizes all conversion logic and supports:

- Converting from common History to OpenAI-specific ChatCompletionMessageParam objects
- Converting from OpenAI-specific ChatCompletionMessageParam objects to common Message objects
- Creating provider-specific messages from chunks or tool results
- Creating wrappers for OpenAI's streaming content chunks

## Message Mapping

| Common Format | OpenAI Format |
|---------------|---------------|
| History.system_message | ChatCompletionSystemMessageParam(role='system', content=[ContentPartTextParam]) |
| History.context | ChatCompletionUserMessageParam(role='user', content=[ContentPartTextParam]) |
| Message(role=USER, content=[ContentPartText]) | ChatCompletionUserMessageParam(role='user', content=[ContentPartTextParam]) |
| Message(role=MODEL, content=[ContentPartText, ContentPartToolCall]) | ChatCompletionAssistantMessageParam(role='assistant', content=text_parts, tool_calls=tool_calls) |
| Message(role=TOOL, content=[ContentPartToolResult]) | ChatCompletionToolMessageParam(role='tool', tool_call_id=id, content=json_content) |

## Role Mapping

| Common Format | OpenAI Format |
|---------------|---------------|
| Role.SYSTEM | "system" |
| Role.USER | "user" |
| Role.MODEL | "assistant" |
| Role.TOOL | "tool" |

## Tool Call Structure

OpenAI uses a specific structure for tool calls and results:

1. **Tool Calls**: Part of an assistant message as `tool_calls` with:
   - `id`: The unique identifier for the tool call
   - `function.name`: The name of the function to call
   - `function.arguments`: JSON string of arguments

2. **Tool Results**: Separate messages with:
   - `role`: "tool"
   - `tool_call_id`: Reference to the original tool call
   - `content`: JSON string result of the tool execution

## Example Flow

1. The application creates a common format History object
2. The converter transforms it to OpenAI ChatCompletionMessageParam objects via `from_history()`
3. The OpenAI API client receives and processes these objects
4. Responses from OpenAI are wrapped in ChoiceDeltaWrapper
5. Tool calls and results are processed through the converter
6. The conversation history is updated using `to_history()`