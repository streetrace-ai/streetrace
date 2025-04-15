# Ollama Message Format Conversion

This document explains how messages are converted between the common internal format and the Ollama-specific format.

## Ollama Message Format

Ollama follows a format similar to OpenAI's Chat API, with some differences:

```json
[
  {
    "role": "system",
    "content": "You are a helpful assistant."
  },
  {
    "role": "user",
    "content": "Hello, who are you?"
  },
  {
    "role": "assistant",
    "content": "I'm an AI assistant powered by Ollama. How can I help you today?"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_123",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\":\"San Francisco\",\"unit\":\"celsius\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "get_weather",
    "content": "{\"temperature\": 22, \"unit\": \"celsius\", \"description\": \"Sunny\"}"
  }
]
```

## Common Internal Format

The internal representation uses a `History` object with a list of `Message` objects, each containing a list of `ContentPart` objects.

```python
History(
    system_message="You are a helpful assistant.",
    context="Project context here",
    conversation=[
        Message(
            role=Role.USER,
            content=[ContentPartText(text="Hello, who are you?")]
        ),
        Message(
            role=Role.MODEL,
            content=[ContentPartText(text="I'm an AI assistant powered by Ollama. How can I help you today?")]
        ),
        Message(
            role=Role.MODEL,
            content=[
                ContentPartToolCall(
                    id="call_123",
                    name="get_weather",
                    arguments={"location": "San Francisco", "unit": "celsius"}
                )
            ]
        ),
        Message(
            role=Role.TOOL,
            content=[
                ContentPartToolResult(
                    id="call_123",
                    name="get_weather",
                    content={"temperature": 22, "unit": "celsius", "description": "Sunny"}
                )
            ]
        )
    ]
)
```

## Conversion Mapping

| Common Format | Ollama Format |
|---------------|---------------|
| `History.system_message` | First message with `"role": "system"` |
| `History.context` | First/Second message with `"role": "user"` |
| `Message(role=Role.USER)` with `ContentPartText` | `{"role": "user", "content": "..."}` |
| `Message(role=Role.MODEL)` with `ContentPartText` | `{"role": "assistant", "content": "..."}` |
| `Message(role=Role.MODEL)` with `ContentPartToolCall` | `{"role": "assistant", "tool_calls": [{"function": {"name": "...", "arguments": "..."}}]}` |
| `Message(role=Role.TOOL)` with `ContentPartToolResult` | `{"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}` |

## Stream Processing

For streaming responses, the `OllamaResponseChunkWrapper` implements the `ChunkWrapper` interface to provide consistent access to text and tool calls across different providers:

1. `get_text()`: Extracts the text from a message content chunk
2. `get_tool_calls()`: Extracts any tool calls from a message chunk

This allows the application to process streaming responses in a provider-agnostic way.