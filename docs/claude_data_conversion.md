# Claude Data Conversion Guide

This document explains the data format conversions that take place in the Claude implementation of the LLMAPI interface.

## Data Formats

There are three main data formats involved in the Claude integration:

1. **Common Format** (defined in `llm/wrapper.py`):
   - Used across all providers
   - Includes types like `History`, `Message`, `ContentPartText`, `ContentPartToolCall`, etc.

2. **Provider Input Format** (Claude-specific):
   - The format required by Claude API's `client.messages.create()` method
   - Uses Anthropic's types like `MessageParam`, `TextBlockParam`, `ToolUseBlockParam`

3. **Provider Response Format** (Claude-specific):
   - The format returned by Claude API's response
   - Includes types like `ContentBlock`, `TextBlock`, `ToolUseBlock`

## Data Flow

The data flow in the Claude implementation follows these steps:

1. **Common Format → Provider Input Format**:
   - Main method: `transform_history()`
   - Helper method: `_common_to_claude_content_part()`
   - Converts our internal message history to Claude-compatible messages

2. **Provider Response → Processing**:
   - `ContentBlockChunkWrapper` class wraps Claude's ContentBlock objects
   - Provides standard access to text and tool calls

3. **Processing → Common Format**:
   - Main method: `update_history()`
   - Helper method: `_claude_to_common_content_part()`
   - Converts Claude's response format back to our common format

4. **Response Processing → Provider History**:
   - Main method: `append_to_history()`
   - Helper method: `_content_block_to_message_param()`
   - Adds processed responses back to the provider-specific history

## Conversion Helpers

The Claude implementation includes several helper methods to manage these conversions:

- `_common_to_claude_content_part()`: Converts common format content parts to Claude format
- `_claude_to_common_content_part()`: Converts Claude format content parts to common format
- `_extract_tool_use_names()`: Extracts tool use IDs and names for reference when processing tool results
- `_content_block_to_message_param()`: Converts content blocks to Claude message parameters

## Testing

The conversion logic is tested in `tests/test_claude_transform_history.py`, which verifies:

1. Transformation from common history to Claude format
2. Updating common history based on Claude format
3. Converting individual content parts between formats
4. Handling special cases like empty context

## Implementation Notes

- The Claude implementation preserves all necessary metadata through conversions
- Tool use IDs and names are tracked to properly associate tool results with their calls
- The conversions maintain message role information (user/assistant)
- Context messages are handled specially in both conversions