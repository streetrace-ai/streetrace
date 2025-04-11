# Claude Data Conversion Design

This document explains the data conversion flow between the common message format and Claude-specific formats in the StreetRace project.

## Overview

The StreetRace project uses multiple LLM providers (Claude, Gemini, OpenAI, Ollama) through a common interface. Each provider must handle conversions between:

1. **Common Format**: Defined in `llm/wrapper.py` - a provider-agnostic format used throughout the application
2. **Provider Input Format**: The specific message format required by the provider's API
3. **Provider Response Format**: The format returned by the provider's API

## Type Converter Abstract Base Class

The project now uses an abstract base class `TypeConverter` in `llm/type_converter.py` that defines the interface for all provider-specific converters. This ensures consistent behavior across different LLM implementations.

The `TypeConverter` is generic with two type parameters:
- `T_MessageParam`: The provider-specific message parameter type
- `T_ContentBlockParam`: The provider-specific content block parameter type

## Data Flow

The data flow for Claude is now centralized through the `ClaudeConverter` class that implements the `TypeConverter` interface:

```
Common Format (History) → Claude Format (MessageParam) → API Call → 
Claude Response (ContentBlock) → Common Format (History)
```

## Conversion Components

### `ClaudeConverter` Class

This class centralizes all conversion logic in `llm/claude_converter.py` and implements the `TypeConverter` interface:

- **`_from_content_part`**: Converts common format content parts to Claude format
- **`_to_content_part`**: Converts Claude format content parts to common format
- **`from_history`**: Converts entire common format history to Claude format
- **`to_history`**: Converts Claude format history to common format
- **`to_history_item`**: Creates a provider-specific message from chunks or tool results
- **`_content_blocks_to_message`**: Creates an assistant message from content chunks
- **`_tool_results_to_message`**: Creates a tool results message from tool results

### `Claude` Class

The `Claude` class in `llm/claude.py` uses `ClaudeConverter` for all conversions:

- **`transform_history`**: Uses `ClaudeConverter.from_history`
- **`update_history`**: Uses `ClaudeConverter.to_history`
- **`append_to_history`**: Uses `ClaudeConverter.to_history_item`

## Benefits of This Approach

1. **Abstraction**: Common interface for all provider converters
2. **Type Safety**: Generic type parameters ensure correct type usage
3. **Centralized Logic**: All conversion code is in one place, making it easier to maintain
4. **Clear Data Flow**: The path from common format to provider format and back is explicit
5. **Reusable Components**: Conversion functions can be reused throughout the codebase
6. **Easier Testing**: Isolated conversion logic can be tested independently
7. **Extensibility**: New providers can be added by implementing the TypeConverter interface

## Type Definitions

- **Common Format**:
  - `History`: Container for system message, context, and conversation
  - `Message`: Role and content parts
  - `ContentPart`: Interface for different content types (text, tool calls, tool results)

- **Claude Format**:
  - `anthropic.types.MessageParam`: Claude's message format
  - `anthropic.types.ContentBlockParam`: Claude's content block format
  - `anthropic.types.ContentBlock`: Claude's response content format

## Example Usage

The data conversion flow in a typical interaction:

1. **Start**: Application has conversation history in common format
2. **Request**: `transform_history` converts to Claude format for API request
3. **Response**: Claude API returns response in Claude format
4. **Process**: Process chunks through `ContentBlockChunkWrapper`
5. **Update**: `append_to_history` adds processed chunks to provider history
6. **Synchronize**: `update_history` updates common format history with provider history

## Future Improvements

Future improvements could include:

1. Implement specific TypeConverter implementations for other providers (OpenAI, Gemini, Ollama)
2. Better token counting for conversation management
3. Enhanced error handling for conversion edge cases
4. Streaming support for responses
5. Performance optimizations for large conversation histories