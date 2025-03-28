import os
import logging
import anthropic  # pip install anthropic
import json
import time
from colors import AnsiColors

# Constants
MAX_TOKENS = 200000  # Claude 3 Sonnet has a context window of approximately 200K tokens
MODEL_NAME = "claude-3-7-sonnet-20250219"

# Initialize API client
def initialize_client():
    """Initialize and return the Claude API client."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
    return anthropic.Anthropic(api_key=api_key)

def transform_tools(tools):
    """
    Transform tools from common format to Claude-specific format.
    
    Args:
        tools (list): List of tool definitions in common format
        
    Returns:
        list: List of tool definitions in Claude format
    """
    claude_tools = []
    
    for tool in tools:
        claude_tool = {
            "type": "custom",
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": tool["parameters"]["required"]
            }
        }
        
        # Transform parameters
        for param_name, param_def in tool["parameters"]["properties"].items():
            claude_tool["input_schema"]["properties"][param_name] = {
                "type": param_def["type"],
                "description": param_def["description"]
            }
        
        claude_tools.append(claude_tool)
    
    return claude_tools

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

def generate_with_tool(prompt, tools, call_tool, conversation_history=None, model_name=MODEL_NAME, system_message=None):
    """
    Generates content using the Claude model with tools,
    maintaining conversation history.
    
    Args:
        prompt (str): The user's input prompt
        tools (list): List of tool definitions in common format.
        call_tool (function): Function to call for tool execution.
        conversation_history (list, optional): The history of the conversation. Defaults to None.
        model_name (str, optional): The name of the Claude model to use. Defaults to MODEL_NAME.
        system_message (str, optional): The system message to use. If None, a default will be used.
    
    Returns:
        list: The updated conversation history
    """
    # Initialize client and conversation history
    client = initialize_client()
    if conversation_history is None:
        conversation_history = []

    # Use default system message if none is provided
    if system_message is None:
        system_message = """You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications."""

    # Log and display user prompt
    print(AnsiColors.USER + prompt + AnsiColors.RESET)
    logging.info("User prompt: %s", prompt)

    # Add the user's prompt to the conversation history
    user_message = {
        'role': 'user',
        'content': [{
            'type': 'text',
            'text': prompt
        }]
    }
    conversation_history.append(user_message)
    messages = conversation_history.copy()

    # Ensure messages are within token limits
    if not manage_conversation_history(messages):
        print(AnsiColors.MODELERROR + "Conversation too large, cannot continue." + AnsiColors.RESET)
        return conversation_history

    continue_generation = True
    request_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    last_response = None

    while continue_generation:
        retry_count = 0
        while True:  # This loop handles retries for rate limit errors
            try:
                request_count += 1
                logging.info(
                    f"Starting chunk processing {request_count} with {len(messages)} message items."
                )
                logging.debug("Messages for generation:\n%s", pretty_print(messages))

                # Create the message with Claude
                last_response = client.messages.create(
                    model=model_name,
                    max_tokens=20000,
                    system=system_message,
                    messages=messages,
                    tools=transform_tools(tools))

                logging.debug("Full API response: %s", last_response)
                
                if last_response.usage:
                    total_input_tokens += last_response.usage.input_tokens
                    total_output_tokens += last_response.usage.output_tokens
                
                # Break the retry loop if successful
                break
                
            except anthropic.RateLimitError as e:
                retry_count += 1
                wait_time = 30  # Wait for 30 seconds before retrying
                
                error_msg = f"Rate limit error encountered. Retrying in {wait_time} seconds... (Attempt {retry_count})"
                logging.warning(error_msg)
                print(AnsiColors.WARNING + error_msg + AnsiColors.RESET)
                
                time.sleep(wait_time)
                continue
                
            except Exception as e:
                logging.exception(f"Error during API call: {e}")
                print(AnsiColors.MODELERROR +
                      f"\nError during API call: {e}" +
                      AnsiColors.RESET)
                # For non-rate limit errors, don't retry
                raise

        model_messages = []
        tool_results = []

        for content_block in last_response.content:
            model_messages.append(content_block)
            if content_block.type == 'text':
                print(AnsiColors.MODEL + content_block.text +
                    AnsiColors.RESET, end='')
            elif content_block.type == 'tool_use':
                call_name = content_block.name
                call_args = content_block.input
                print(AnsiColors.TOOL + f"{call_name}: {call_args}" + AnsiColors.RESET)
                logging.info(f"Tool call: {call_name} with {call_args}")

                # Execute the tool
                tool_result = call_tool(call_name, call_args, content_block)

                # Add tool result to outputs
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': content_block.id,
                    'content': json.dumps(tool_result) 
                })
                
        messages.append({
            'role': last_response.role,
            'content': model_messages})
        messages.append({
            'role': 'user',
            'content': tool_results})

        conversation_history[len(conversation_history):len(messages)] = messages[len(conversation_history):]

        # Continue only if there were tool calls
        continue_generation = last_response.stop_reason == 'tool_use'

    if last_response:
        print("\n" + AnsiColors.MODEL + f"Stop reason: {last_response.stop_reason}" +
              AnsiColors.RESET)
        logging.info(f"Model has finished with reason: {last_response.stop_reason}")

    return conversation_history