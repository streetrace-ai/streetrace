import os
import logging
import anthropic  # pip install anthropic
import json
import time
import tools.fs_tool as fs_tool

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='claude_generation.log'
)

# ANSI color codes for terminal output
class AnsiColors:
    USER = '\x1b[1;32;40m'
    MODEL = '\x1b[1;37;40m'
    MODELERROR = '\x1b[1;37;41m'
    TOOL = '\x1b[1;34;40m'
    TOOLERROR = '\x1b[1;34;41m'
    DEBUG = '\x1b[0;35;40m'
    RESET = '\x1b[0m'
    WARNING = '\x1b[1;33;40m'

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

# Tool definitions
TOOLS = [{
    "type": "custom",
    "name": "search_files",
    "description":
    "Searches for text occurrences in files given a glob pattern and a search string.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files."
            },
            "search_string": {
                "type": "string",
                "description": "The string to search for."
            }
        },
        "required": ["pattern", "search_string"]
    }
}, {
    "type": "custom",
    "name": "execute_cli_command",
    "description":
    "Executes a CLI command and returns the output, error, and return code.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The CLI command to execute."
            }
        },
        "required": ["command"]
    }
}, {
    "type": "custom",
    "name": "write_file",
    "description":
    "Write content to a file. Overwrites the file if it already exists.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write to."
            },
            "content": {
                "type": "string",
                "description": "New content of the file."
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding to use. Defaults to \"utf-8\"."
            }
        },
        "required": ["path", "content"]
    }
}, {
    "type": "custom",
    "name": "read_file",
    "description": "Read file contents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description":
                "Path to the file to retrieve the contents from."
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding to use. Defaults to \"utf-8\"."
            }
        },
        "required": ["path"]
    }
}, {
    "type": "custom",
    "name": "list_directory",
    "description":
    "List information about the files and directories in the requested directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type":
                "string",
                "description":
                "Path to the directory to retrieve the contents from."
            }
        },
        "required": ["path"]
    }
}]

# Map tool names to functions
TOOLS_DICT = {
    'list_directory': fs_tool.list_directory,
    'read_file': fs_tool.read_file,
    'write_file': fs_tool.write_file,
    'execute_cli_command': fs_tool.execute_cli_command,
    'search_files': fs_tool.search_files
}

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

def handle_tool_call(content_block):
    """
    Process a tool call and return its result.
    
    Args:
        content_block: The tool call object from Claude
        
    Returns:
        dict: Result of the tool call
    """
    if content_block.name not in TOOLS_DICT:
        error_msg = f"Missing function: {content_block.name}"
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.error(error_msg)
        return {"error": error_msg}
        
    try:
        logging.debug(f"Calling function {content_block.name} with arguments: {content_block.input}")
        result = TOOLS_DICT[content_block.name](**content_block.input)
        print(AnsiColors.TOOL + str(result) + AnsiColors.RESET)
        logging.info(f"Function result: {result}")
        return {"result": result}
    except Exception as e:
        error_msg = f"Error in {content_block.name}: {str(e)}"
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.warning(error_msg)
        return {"error": str(e)}

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

def generate_with_tool(prompt, conversation_history=None, model_name=MODEL_NAME, system_message=None):
    """
    Generates content using the Claude model with tools,
    maintaining conversation history.
    
    Args:
        prompt (str): The user's input prompt
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
                    tools=TOOLS)

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
                print(AnsiColors.TOOL + content_block.name + ": " +
                      str(content_block.input) + AnsiColors.RESET)
                logging.info(f"Tool call: {content_block}")

                # Execute the tool
                tool_result = handle_tool_call(content_block)

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
        print(AnsiColors.MODEL + f"Stop reason: {last_response.stop_reason}" +
              AnsiColors.RESET)
        logging.info(f"Model has finished with reason: {last_response.stop_reason}")

    return conversation_history