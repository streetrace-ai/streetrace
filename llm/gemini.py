"""
Gemini AI Provider Implementation

This module implements the LLMAPI interface for Google's Gemini models.
"""

import os
import logging
from typing import List, Dict, Any, Callable, Optional, Union

from google import genai
from google.genai import types
from colors import AnsiColors
from llm.llmapi import LLMAPI

# Constants
MAX_TOKENS = 2**20
MODEL_NAME = 'gemini-2.5-pro-exp-03-25'
MAX_MALFORMED_RETRIES = 3  # Maximum number of retries for malformed function calls


class Gemini(LLMAPI):
    """
    Implementation of the LLMAPI interface for Google's Gemini models.
    """
    
    def initialize_client(self) -> genai.Client:
        """
        Initialize and return the Gemini API client.
        
        Returns:
            genai.Client: The initialized Gemini client
            
        Raises:
            ValueError: If GEMINI_API_KEY environment variable is not set
        """
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        return genai.Client(api_key=api_key)

    def transform_tools(self, tools: List[Dict[str, Any]]) -> List[types.Tool]:
        """
        Transform tools from common format to Gemini-specific format.
        
        Args:
            tools: List of tool definitions in common format
            
        Returns:
            List[types.Tool]: List of tool definitions in Gemini format
        """
        gemini_tools = []
        
        for tool in tools:
            # Convert properties to Gemini Schema format
            gemini_properties = {}
            for param_name, param_def in tool['function']['parameters']['properties'].items():
                if 'items' in param_def:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def['type'].upper(),  # Gemini uses uppercase type names
                        items=types.Schema(
                            type=param_def['items']['type'].upper(),  # Gemini uses uppercase type names
                        ),
                        description=param_def['description']
                    )
                else:
                    gemini_properties[param_name] = types.Schema(
                        type=param_def['type'].upper(),  # Gemini uses uppercase type names
                        description=param_def['description']
                    )
            
            # Create the function declaration
            function_declaration = types.FunctionDeclaration(
                name=tool['function']['name'],
                description=tool['function']['description'],
                parameters=types.Schema(
                    description=f'Parameters for the {tool['function']['name']} function',
                    type='OBJECT',
                    properties=gemini_properties,
                    required=tool['function']['parameters']['required']
                )
            )
            
            # Add the tool to the list
            gemini_tools.append(types.Tool(function_declarations=[function_declaration]))
        
        return gemini_tools

    def pretty_print(self, contents: List[types.Content]) -> str:
        """
        Format content list for readable logging.
        
        Args:
            contents: List of content objects to format
            
        Returns:
            str: Formatted string representation
        """
        parts = []
        for i, content in enumerate(contents):
            if not content:
                parts.append(f"Content {i + 1}:\nNONE")
                continue
                
            content_parts = []
            for part in content.parts:
                part_attrs = ", ".join(
                    [f"{attr}: {str(val).strip()}" 
                     for attr, val in part.__dict__.items() 
                     if val is not None]
                )
                content_parts.append(part_attrs)
                
            parts.append(f"Content {i + 1}:\n - {content.role}: {'; '.join(content_parts)}")
            
        return "\n".join(parts)

    def manage_conversation_history(
        self, 
        conversation_history: List[Any], 
        max_tokens: int = MAX_TOKENS
    ) -> bool:
        """
        Ensure contents are within token limits by intelligently pruning when needed.
        
        Args:
            conversation_history: List of content objects to manage
            max_tokens: Maximum token limit
            
        Returns:
            bool: True if successful, False if pruning failed
        """
        try:
            client = self.initialize_client()
            token_count = client.models.count_tokens(model=MODEL_NAME, contents=conversation_history)
            
            # If within limits, no action needed
            if token_count.total_tokens <= max_tokens:
                return True
                
            logging.info(f"Token count {token_count.total_tokens} exceeds limit {max_tokens}, pruning...")
            
            # Keep first item (usually system message) and last N exchanges
            if len(conversation_history) > 3:
                # Keep important context - first message and recent exchanges
                preserve_count = min(5, len(conversation_history) // 2)
                conversation_history[:] = [conversation_history[0]] + conversation_history[-preserve_count:]
                
                # Recheck token count
                token_count = client.models.count_tokens(model=MODEL_NAME, contents=conversation_history)
                logging.info(f"After pruning: {token_count.total_tokens} tokens with {len(conversation_history)} items")
                
                return token_count.total_tokens <= max_tokens
            
            # If conversation is small but still exceeding, we have a problem
            logging.warning(f"Cannot reduce token count sufficiently: {token_count.total_tokens}")
            return False
            
        except Exception as e:
            logging.error(f"Error managing tokens: {e}")
            return False

    def generate_with_tool(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        call_tool: Callable,
        conversation_history: Optional[List[Any]] = None,
        model_name: Optional[str] = MODEL_NAME,
        system_message: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> List[Any]:
        """
        Generates content using the Gemini model with tools, maintaining conversation history.
        
        Args:
            prompt: The user's input prompt
            tools: List of tool definitions in common format
            call_tool: Function to call for tool execution
            conversation_history: The history of the conversation
            model_name: The name of the Gemini model to use
            system_message: The system message to use
            project_context: Additional project context to be added to the user's prompt
            
        Returns:
            List[Any]: The updated conversation history
        """
        # Get malformed retries if provided in kwargs
        malformed_retries = 3
        
        # Initialize client and conversation history
        client = self.initialize_client()
        if conversation_history is None:
            conversation_history = []

        model_name = model_name or MODEL_NAME

        # Use default system message if none is provided
        system_message = system_message or """You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications."""

        # Add project context to the conversation history
        if project_context:
            print(AnsiColors.USER + "[Adding project context]" + AnsiColors.RESET)
            logging.debug(f"Context: {project_context}")
            conversation_history.append(types.Content(
                role='user',
                parts=[types.Part.from_text(text=project_context)]
            ))

        # Add the user's prompt to the conversation history
        if prompt:
            print(AnsiColors.USER + prompt + AnsiColors.RESET)
            logging.info(f"User prompt: {prompt}")
            conversation_history.append(types.Content(
                role='user',
                parts=[types.Part.from_text(text=prompt)]
            ))

        contents = conversation_history.copy()

        # Ensure contents are within token limits
        if not self.manage_conversation_history(contents, MAX_TOKENS):
            print(AnsiColors.MODELERROR + "Conversation too large, cannot continue." + AnsiColors.RESET)
            return conversation_history

        # Process generation requests
        try:
            # Set up generation configuration
            generation_config = types.GenerateContentConfig(
                tools=self.transform_tools(tools),
                system_instruction=system_message,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode='AUTO')
                )
            )
            
            # Stream and process the response
            request_parts = []
            response_parts = []
            response_text = ''
            
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=generation_config
            ):
                logging.debug(f"Chunk received: {chunk}")
                
                # Track finish information
                try:
                    finish_reason = chunk.candidates[0].finish_reason or 'None'
                    finish_message = chunk.candidates[0].finish_message or 'None'
                except (AttributeError, IndexError):
                    finish_reason = 'unknown'
                    finish_message = 'unknown'
                
                # Handle text output
                if hasattr(chunk, 'text') and chunk.text:
                    print(AnsiColors.MODEL + chunk.text + AnsiColors.RESET, end='')
                    response_text += chunk.text
                
                # Handle function calls
                if hasattr(chunk, 'function_calls') and chunk.function_calls:
                    # If we have text, add it to the request parts
                    if response_text.strip():
                        request_parts.append(types.Part(text=response_text))
                        response_text = ''
                    
                    # Process all function calls in the chunk
                    for function_call in chunk.function_calls:
                        call_name = function_call.name
                        call_args = function_call.args
                        print(AnsiColors.TOOL + f"{call_name}: {call_args}" + AnsiColors.RESET)
                        logging.info(f"Tool call: {call_name} with {call_args}")
                        
                        # Add the function call to request parts
                        request_parts.append(types.Part(function_call=function_call))
                        
                        # Execute the tool
                        tool_result = call_tool(call_name, call_args, function_call)
                        
                        # Add the function response to response parts
                        response_parts.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=function_call.id,
                                    name=function_call.name,
                                    response=tool_result
                                )
                            )
                        )
            
            # Capture any remaining text
            if response_text.strip():
                request_parts.append(types.Part(text=response_text))
            
            # Create content objects for model and tool responses
            model_response_content = types.Content(
                role='model',
                parts=request_parts
            )
            conversation_history.append(model_response_content)
            
            # Handle MALFORMED_FUNCTION_CALL finish reason
            if finish_reason == 'MALFORMED_FUNCTION_CALL':
                logging.info(f"Received MALFORMED_FUNCTION_CALL (attempt {malformed_retries + 1}/{MAX_MALFORMED_RETRIES})")
                
                # If we haven't hit the maximum retries, try again
                if malformed_retries < MAX_MALFORMED_RETRIES - 1:
                    print(AnsiColors.MODELERROR + 
                          f"Malformed function call detected (attempt {malformed_retries + 1}/{MAX_MALFORMED_RETRIES}). Retrying..." + 
                          AnsiColors.RESET)
                    
                    # Retry with empty prompt but send the last model response back
                    return self.generate_with_tool('', tools, call_tool, conversation_history, 
                                             model_name, system_message, project_context, 
                                             malformed_retries=malformed_retries + 1)
                else:
                    print(AnsiColors.MODELERROR + 
                          f"Maximum malformed function call retries ({MAX_MALFORMED_RETRIES}) reached. Stopping." + 
                          AnsiColors.RESET)
            
            # If there were function calls, add tool responses to history
            if response_parts:
                tool_response_content = types.Content(
                    role='tool',
                    parts=response_parts
                )
                conversation_history.append(tool_response_content)
                
                # Continue with function call results
                return self.generate_with_tool('', tools, call_tool, conversation_history, model_name, system_message)
            
            # Output finish information
            print("\n" + AnsiColors.MODEL + f"{finish_reason}: {finish_message}" + AnsiColors.RESET)
            logging.info(f"Model finished with reason {finish_reason}: {finish_message}")
        
        except Exception as e:
            error_msg = f"Error during content generation: {e}"
            logging.error(error_msg)
            print(AnsiColors.MODELERROR + error_msg + AnsiColors.RESET)
        
        return conversation_history