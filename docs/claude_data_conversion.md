# Anthropic Data Conversion Guide

This document explains the data format conversions that take place in the Anthropic implementation of the LLMAPI interface.

## Data Formats

There are three main data formats involved in the Anthropic integration:

1. **Common Format** (defined in `llm/wrapper.py`):
   - Used across all providers
   - Includes types like `History`, `Message`, `ContentPartText`, `ContentPartToolCall`, etc.

2. **Provider Input Format** (Anthropic-specific):
   - The format required by Anthropic API's `client.messages.create()` method
   - Uses Anthropic's types like `MessageParam`, `TextBlockParam`, `ToolUseBlockParam`

3. **Provider Response Format** (Anthropic-specific):
   - The format returned by Anthropic API's response
   - Includes types like `ContentBlock`, `TextBlock`, `ToolUseBlock`

## Data Flow

The data flow in the Anthropic implementation follows these steps:

1. **Common Format → Provider Input Format**:
   - Main method: `transform_history()`
   - Helper method: `_common_to_claude_content_part()`
   - Converts our internal message history to Anthropic-compatible messages

2. **Provider Response → Processing**:
   - `ContentBlockChunkWrapper` class wraps Anthropic's ContentBlock objects
   - Provides standard access to text and tool calls

3. **Processing → Common Format**:
   - Main method: `update_history()`
   - Helper method: `_claude_to_common_content_part()`
   - Converts Anthropic's response format back to our common format

4. **Response Processing → Provider History**:
   - Main method: `append_to_history()`
   - Helper method: `_content_block_to_message_param()`
   - Adds processed responses back to the provider-specific history

## Conversion Helpers

The Anthropic implementation includes several helper methods to manage these conversions:

- `_common_to_claude_content_part()`: Converts common format content parts to Anthropic format
- `_claude_to_common_content_part()`: Converts Anthropic format content parts to common format
- `_extract_tool_use_names()`: Extracts tool use IDs and names for reference when processing tool results
- `_content_block_to_message_param()`: Converts content blocks to Anthropic message parameters

## Testing

The conversion logic is tested in `tests/test_claude_transform_history.py`, which verifies:

1. Transformation from common history to Anthropic format
2. Updating common history based on Anthropic format
3. Converting individual content parts between formats
4. Handling special cases like empty context

## Implementation Notes

- The Anthropic implementation preserves all necessary metadata through conversions
- Tool use IDs and names are tracked to properly associate tool results with their calls
- The conversions maintain message role information (user/assistant)
- Context messages are handled specially in both conversions