"""
AI Provider Interface Module

This module defines the abstract base class LLMAPI that serves as a common interface
for different AI model providers (Claude, Gemini, OpenAI, Ollama). It standardizes
initialization, API calls, and tool management across all providers.
"""

import abc
from typing import List, Dict, Any, Callable, Optional


class LLMAPI(abc.ABC):
    """
    Abstract base class for AI model providers.
    
    This class defines a common interface that all AI providers must implement,
    standardizing how we initialize clients, transform tools, manage conversations,
    and generate content with tools.
    """
    
    @abc.abstractmethod
    def initialize_client(self) -> Any:
        """
        Initialize and return the AI provider client.
        
        Returns:
            Any: The initialized client object
            
        Raises:
            ValueError: If required API keys or configuration is missing
        """
        pass
    
    @abc.abstractmethod
    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform tools from common format to provider-specific format.
        
        Args:
            tools: List of tool definitions in common format
            
        Returns:
            List[Dict[str, Any]]: List of tool definitions in provider-specific format
        """
        pass
    
    @abc.abstractmethod
    def pretty_print(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format message list for readable logging.
        
        Args:
            messages: List of message objects to format
            
        Returns:
            str: Formatted string representation
        """
        pass
    
    @abc.abstractmethod
    def manage_conversation_history(self, conversation_history: List[Dict[str, Any]], max_tokens: int) -> bool:
        """
        Ensure conversation history is within token limits by intelligently pruning when needed.
        
        Args:
            conversation_history: List of message objects to manage
            max_tokens: Maximum token limit
            
        Returns:
            bool: True if successful, False if pruning failed
        """
        pass
    
    @abc.abstractmethod
    def generate_with_tool(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        call_tool: Callable,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        model_name: Optional[str] = None,
        system_message: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates content using the AI model with tools, maintaining conversation history.
        
        Args:
            prompt: The user's input prompt
            tools: List of tool definitions in common format
            call_tool: Function to call for tool execution
            conversation_history: The history of the conversation
            model_name: The name of the AI model to use
            system_message: The system message to use
            project_context: Additional project context to be added to the user's prompt
            
        Returns:
            List[Dict[str, Any]]: The updated conversation history
        """
        pass