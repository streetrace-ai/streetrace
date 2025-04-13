# Gemini Converter

The Gemini converter is responsible for translating between StreetRace's common message format and Google's Gemini API-specific format. This allows the rest of the application to use a consistent interface regardless of which AI provider is being used.

## Core Components

### GenerateContentPartWrapper

A wrapper class for Gemini's `Part` objects that implements the `ChunkWrapper` interface. This provides a consistent way to access content from Gemini's responses, including:

- Text content via `get_text()`
- Tool/function calls via `get_tool_calls()`

### GeminiConverter

The main converter class that implements the `HistoryConverter` interface for Gemini-specific types. This class centralizes all conversion logic and supports:

- Converting from common History to Gemini-specific Content objects
- Converting from Gemini-specific Content objects to common Message objects
- Creating provider-specific messages from chunks or tool results
- Creating wrappers for Gemini's streaming content chunks

## Message Mapping

| Common Format | Gemini Format |
|---------------|---------------|
| History.context | Content(role='user', parts=[text]) |
| Message(role, content) | Content(role, parts) |
| ContentPartText(text) | Part.from_text(text) |
| ContentPartToolCall(id, name, args) | Part.from_function_call(id, name, args) |
| ContentPartToolResult(id, name, content) | Part.from_function_response(id, name, response) |

## Role Mapping

| Common Format | Gemini Format |
|---------------|---------------|
| assistant | model |
| user | user |
| (tool results) | tool |

## Example Flow

1. The application creates a common format History object
2. The converter transforms it to Gemini Content objects via `from_history()`
3. The Gemini API client receives and processes these objects
4. Responses from Gemini are wrapped in GenerateContentPartWrapper
5. Tool calls and results are processed through the converter
6. The conversation history is updated using `to_history()`