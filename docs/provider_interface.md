# AI Provider Interface

This document explains the AIProvider interface architecture and how to use it in StreetRace.

## Overview

StreetRace has been refactored to use a common interface for all AI providers (Claude, Gemini, OpenAI, Ollama). This design improves code maintainability, makes it easier to add new providers, and provides a consistent way to interact with different AI models.

## Key Components

### 1. AIProvider Abstract Base Class

The `AIProvider` class defined in `ai_interface.py` serves as the foundation for all provider implementations. Each provider must implement these methods:

```python
class AIProvider(abc.ABC):
    @abc.abstractmethod
    def initialize_client(self) -> Any:
        """Initialize and return the AI provider client."""
        pass
    
    @abc.abstractmethod
    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform tools from common format to provider-specific format."""
        pass
    
    @abc.abstractmethod
    def pretty_print(self, messages: List[Dict[str, Any]]) -> str:
        """Format message list for readable logging."""
        pass
    
    @abc.abstractmethod
    def manage_conversation_history(self, conversation_history: List[Dict[str, Any]], max_tokens: int) -> bool:
        """Ensure conversation history is within token limits."""
        pass
    
    @abc.abstractmethod
    def generate_with_tool(self, prompt: str, tools: List[Dict[str, Any]], call_tool: Callable,
                           conversation_history: Optional[List[Dict[str, Any]]] = None,
                           model_name: Optional[str] = None, system_message: Optional[str] = None,
                           project_context: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Generates content using the AI model with tools."""
        pass
```

### 2. Provider Implementations

Each AI provider has its own implementation class:

- `ClaudeProvider` in `claude_provider.py`
- `GeminiProvider` in `gemini_provider.py`
- `OpenAIProvider` in `openai_provider.py`
- `OllamaProvider` in `ollama_provider.py`

These classes implement the methods defined in the `AIProvider` interface, handling the specific requirements of their respective AI services.

### 3. Factory Module

The `ai_provider_factory.py` module provides factory functions for creating and using providers:

```python
def get_ai_provider(provider_name: Optional[str] = None) -> AIProvider:
    """Factory function to get the appropriate AI provider instance."""
    # ...

def generate_with_tool(prompt: str, tools: List[Dict[str, Any]], call_tool: Callable,
                       provider_name: Optional[str] = None, conversation_history = None,
                       model_name = None, system_message = None, project_context = None,
                       **kwargs) -> List[Dict[str, Any]]:
    """Convenience function to generate content using the appropriate AI provider."""
    # ...
```

## Using the Interface

### Basic Usage

The simplest way to use the interface is through the factory functions:

```python
from ai_provider_factory import generate_with_tool
from tools.fs_tool import TOOLS

# Use the factory function to generate content
response = generate_with_tool(
    "List all Python files in this directory",
    TOOLS,
    call_tool_function,  # Your tool call handler function
    provider_name="claude"  # Optional - will auto-detect if not provided
)
```

### Specifying a Provider

You can explicitly specify which provider to use:

```python
from ai_provider_factory import get_ai_provider
from tools.fs_tool import TOOLS

# Get a specific provider
provider = get_ai_provider("gemini")

# Use the provider directly
response = provider.generate_with_tool(
    "Explain the code in main.py",
    TOOLS,
    call_tool_function,
    model_name="gemini-2.5-pro-exp-03-25"
)
```

### Extending with a New Provider

To add a new AI provider:

1. Create a new file (e.g., `new_provider.py`) that implements the `AIProvider` interface:

```python
from ai_interface import AIProvider

class NewProvider(AIProvider):
    def initialize_client(self):
        # Initialize and return the client for your new provider
        pass
    
    def transform_tools(self, tools):
        # Transform tools to your provider's format
        pass
    
    # Implement all other required methods...
```

2. Update the factory function in `ai_provider_factory.py` to include your new provider.

## Migration Notes

When migrating from the old direct implementations to the new interface:

1. The former standalone implementations (`claude.py`, `gemini.py`, etc.) have been refactored into provider classes.
2. The `main.py` file has been updated to use the factory pattern.
3. All function signatures remain compatible with the previous implementations for backwards compatibility.

## Best Practices

1. **Use the Factory**: For most cases, use the `generate_with_tool` function from `ai_provider_factory.py`.
2. **Provider Specifics**: If you need provider-specific functionality, get a provider instance with `get_ai_provider()`.
3. **Extend Responsibly**: When adding new providers, ensure they fully implement the interface.
4. **Token Management**: Each provider handles token limits differently - be aware of these differences when working directly with specific providers.
5. **Testing**: Test your code with multiple providers to ensure compatibility.