# Ollama Implementation Refactoring

## Changes Made

1. **Created new converter module (`llm/ollama/converter.py`)**:
   - Implemented `OllamaResponseChunkWrapper` to handle streaming chunks
   - Implemented `OllamaConverter` to transform between common format and Ollama-specific format
   - Added mapping between common role types and Ollama role types
   - Added support for handling tool calls and tool results

2. **Refactored implementation (`llm/ollama/impl.py`)**:
   - Reorganized the code to match the structure of other providers (Claude, Gemini, OpenAI)
   - Implemented all required methods from the `LLMAPI` abstract base class
   - Added proper typing and docstrings
   - Improved error handling and retries
   - Streamlined the streaming response processing
   - Added `append_to_history` method to handle appending responses to history

3. **Added documentation (`llm/ollama/converter.md`)**:
   - Documented the message format conversion between Ollama and common format
   - Provided examples of both formats
   - Explained the conversion mapping and stream processing

## Benefits of the Refactoring

1. **Consistent Structure**: The Ollama implementation now follows the same structure as the other providers, making it easier to maintain and understand.

2. **Improved Type Safety**: Added proper type annotations matching the abstract interfaces.

3. **Better Separation of Concerns**: 
   - Converter is responsible for format transformations
   - Implementation handles API interactions and provider-specific logic

4. **Enhanced Extensibility**: The modular structure makes it easier to add new features or handle changes in the Ollama API.

5. **Improved Documentation**: Added detailed documentation for the conversion process, similar to the other providers.

## Implementation Details

The refactored implementation now properly handles:
- Conversation history transformation
- Tool calls and tool results
- Streaming responses
- Error handling and retries
- Token management