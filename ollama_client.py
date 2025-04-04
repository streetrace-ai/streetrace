import os
import logging
import time
import json
from colors import AnsiColors

import ollama


# Constants
MAX_TOKENS = 32768  # Default context window for most Ollama models
MODEL_NAME = "llama3:8b"  # Default model

# Base URL for Ollama API
def get_base_url():
    """Get the base URL for Ollama API, defaulting to localhost if not specified."""
    return os.environ.get('OLLAMA_API_URL', 'http://localhost:11434')

# Initialize API client
def initialize_client():
    """Initialize and return the Ollama API client."""
    return ollama.Client(
        host=get_base_url(),
        headers={'x-some-header': 'some-value'}
    )

def transform_tools(tools):
    """
    Transform tools from common format to Ollama-specific format.
    
    Args:
        tools (list): List of tool definitions in common format
        
    Returns:
        list: List of tool definitions in Ollama format
    """
    ollama_tools = tools
    
    return ollama_tools

def pretty_print(messages):
    """
    Format message list for readable logging.
    
    Args:
        messages: List of message objects to format
        
    Returns:
        Formatted string representation
    """
    parts = []
    for i, message in enumerate(messages):
        content_str = str(message.get('content', 'NONE'))
        role = message.get('role', 'unknown')
        parts.append(f"Message {i + 1}:\n - {role}: {content_str}")
        
    return "\n".join(parts)

def manage_conversation_history(conversation_history, max_tokens=MAX_TOKENS):
    """
    Ensure conversation history is within token limits by intelligently pruning when needed.
    
    Args:
        conversation_history: List of message objects to manage
        max_tokens: Maximum token limit
        
    Returns:
        True if successful, False if pruning failed
    """
    try:
        # Simplified token count estimation - would need actual token counting in production
        # This is a placeholder for an actual token counting function
        estimated_tokens = sum(len(str(msg)) for msg in conversation_history) // 4
        
        # If within limits, no action needed
        if estimated_tokens <= max_tokens:
            return True
            
        logging.info(f"Estimated token count {estimated_tokens} exceeds limit {max_tokens}, pruning...")
        
        # Keep first item (usually system message) and last N exchanges
        if len(conversation_history) > 3:
            # Keep important context - first message and recent exchanges
            preserve_count = min(5, len(conversation_history) // 2)
            conversation_history[:] = [conversation_history[0]] + conversation_history[-preserve_count:]
            
            # Recheck token count
            estimated_tokens = sum(len(str(msg)) for msg in conversation_history) // 4
            logging.info(f"After pruning: {estimated_tokens} tokens with {len(conversation_history)} items")
            
            return estimated_tokens <= max_tokens
        
        # If conversation is small but still exceeding, we have a problem
        logging.warning(f"Cannot reduce token count sufficiently: {estimated_tokens}")
        return False
        
    except Exception as e:
        logging.error(f"Error managing tokens: {e}")
        return False

def generate_with_tool(prompt, tools, call_tool, conversation_history=None, model_name=MODEL_NAME, system_message=None, project_context=None):
    """
    Generates content using the Ollama model with tools,
    maintaining conversation history.
    
    Args:
        prompt (str): The user's input prompt
        tools (list): List of tool definitions in common format.
        call_tool (function): Function to call for tool execution.
        conversation_history (list, optional): The history of the conversation. Defaults to None.
        model_name (str, optional): The name of the Ollama model to use. Defaults to MODEL_NAME.
        system_message (str, optional): The system message to use. If None, a default will be used.
        project_context (str, optional): Additional project context to be added to the user's prompt.
    
    Returns:
        list: The updated conversation history
    """
    client = initialize_client()
    
    # Use default system message if none is provided
    if system_message is None:
        system_message = """You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications."""

    # Initialize conversation history if None
    if conversation_history is None:
        conversation_history = []
    
    if len(conversation_history) == 0:
        conversation_history.append({
            'role': 'system',
            'content': system_message,
        })
        
    # Add the user's prompt to the conversation history
    if project_context:
        print(AnsiColors.USER + "[Adding project context]" + AnsiColors.RESET)
        logging.debug(f"Context: {project_context}")
        conversation_history.append({
            'role': 'user',
            'content': project_context
        })
        
    # Add the user's prompt to the conversation history
    if prompt:
        print(AnsiColors.USER + prompt + AnsiColors.RESET)
        logging.info("User prompt: %s", prompt)
        conversation_history.append({
            'role': 'user',
            'content': prompt
        })
    messages = conversation_history.copy()

    # Ensure messages are within token limits
    if not manage_conversation_history(messages):
        print(AnsiColors.MODELERROR + "Conversation too large, cannot continue." + AnsiColors.RESET)
        return conversation_history

    continue_generation = True
    request_count = 0
    ollama_tools = transform_tools(tools)
    print(conversation_history)

    while continue_generation:
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:  # This loop handles retries for errors
            try:
                request_count += 1
                logging.info(
                    f"Starting request {request_count} with {len(messages)} message items."
                )
                logging.debug("Messages for generation:\n%s", pretty_print(messages))

                response = client.chat(model=model_name, messages=messages, tools=ollama_tools, stream=True)
                
                # Process the streamed response
                full_response = ""
                tool_calls = []
                tool_results = []
                
                for chunk in response:
                    if not chunk:
                        continue
                    
                    try:
                        # Process message content
                        if chunk.message:
                            # Handle streaming text output
                            if chunk.message.content:
                                print(AnsiColors.MODEL + chunk.message.content + AnsiColors.RESET, end='')
                                full_response += chunk.message.content
                            
                            # Handle tool calls
                            if chunk.message.tool_calls:
                                for tool_call in chunk.message.tool_calls:
                                    tool_calls.append(tool_call)
                                    function_name = tool_call.function.name
                                    function_args = tool_call.function.arguments
                                    
                                    print(AnsiColors.TOOL + f"{function_name}: {function_args}" + AnsiColors.RESET)
                                    logging.info(f"Tool call: {function_name} with {function_args}")
                                    
                                    # Execute the tool
                                    tool_result = call_tool(function_name, function_args, tool_call)
                                    
                                    # Add tool result to the list
                                    tool_results.append({
                                        "role": "tool",
                                        "name": function_name,
                                        "content": str(tool_result)
                                    })
                        # Check for end of response
                        if chunk.done:
                            break
                    
                    except json.JSONDecodeError as e:
                        logging.warning(f"Error parsing JSON from stream: {e}")
                    except Exception as e:
                        logging.error(f"Error processing response chunk: {e}")
                
                # Add the assistant's response to conversation history
                assistant_message = {
                    'role': 'assistant'
                }
                
                # Only add if we have content
                if full_response.strip():
                    assistant_message['content'] = full_response
                
                if tool_calls:
                    assistant_message['tool_calls'] = tool_calls
                
                messages.append(assistant_message)
                
                if tool_results:
                    messages += tool_results
                
                continue_generation = len(tool_results) > 0
                
                # Break the retry loop if successful
                break
                
            except Exception as e:
                retry_count += 1
                
                if retry_count >= max_retries:
                    error_msg = f"Failed after {max_retries} retries: {e}"
                    logging.error(error_msg)
                    print(AnsiColors.MODELERROR + error_msg + AnsiColors.RESET)
                    return conversation_history

                wait_time = 5 * retry_count  # Increase wait time with each retry
                
                error_msg = f"API error encountered. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries}): {e}"
                logging.warning(error_msg)
                print(AnsiColors.WARNING + error_msg + AnsiColors.RESET)
                
                time.sleep(wait_time)

    conversation_history[len(conversation_history):len(messages)] = messages[len(conversation_history):]
        
    logging.info("Model has finished generating response")
    print("\n" + AnsiColors.MODEL + "Done" + AnsiColors.RESET)

    return conversation_history