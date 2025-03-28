import os
import logging
from google import genai
from google.genai import types
import tools.fs_tool as fs_tool

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='generation.log'
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

# Constants
MAX_TOKENS = 2**20
MODEL_NAME = 'gemini-2.0-flash-001'

# Initialize API client
def initialize_client():
    """Initialize and return the Gemini API client."""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    return genai.Client(api_key=api_key)

# System prompt
SYSTEM = """
You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications.
For every step, remember to adhere to the SYSTEM MESSAGE.
You are working with source code in the current directory (./) that you can access using the provided tools.
For every request, understand what needs to be done, then execute the next appropriate action.

1. Please use provided functions to retrieve the required information.
2. Please use provided functions to apply the necessary changes to the project.
3. When you need to implement code, follow best practices for the given programming language.
4. When applicable, follow software and integration design patterns.
5. When applicable, follow SOLID principles.
6. Document all the code you implement.
7. If there is no README.md file, create it describing the project.
8. Create other documentation files as necessary, for example to describe setting up the environment.
9. Create unit tests when applicable. If you can see existing unit tests in the codebase, always create unit tests for new code, and maintain the existing tests.
10. Run the unit tests and static analysis checks, such as lint, to make sure the task is completed.
11. After completing the task, please provide a summary of the changes made and update the documentation.

Remember, the code is located in the current directory (./) that you can access using the provided tools.
Remember, if you can't find a specific location in code, try searching through files for close matches.
Remember, always think step by step and execute one step at a time.
Remember, never commit the changes.
"""

# Tool definitions
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.list_directory',
            description='List information about the files and directories in the requested directory.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the directory to retrieve the contents from.'
                    )
                },
                required=['path']
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.read_file',
            description='Read file contents.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the file to retrieve the contents from.'
                    ),
                    'encoding': types.Schema(
                        type='STRING',
                        description='Text encoding to use. Defaults to \"utf-8\".'
                    )
                },
                required=['path']
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.write_file',
            description='Write content to a file. Overwrites the file if it already exists.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the file to write to.'
                    ),
                    'content': types.Schema(
                        type='STRING',
                        description='New content of the file.'
                    ),
                    'encoding': types.Schema(
                        type='STRING',
                        description='Text encoding to use. Defaults to \"utf-8\".'
                    )
                },
                required=['path', 'content']
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.execute_cli_command',
            description='Executes a CLI command and returns the output, error, and return code.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'command': types.Schema(
                        type='STRING',
                        description='The CLI command to execute.'
                    )
                },
                required=['command']
            )
        )
    ]),
    
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.search_files',
            description='Searches for text occurrences in files given a glob pattern and a search string.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'pattern': types.Schema(
                        type='STRING',
                        description='Glob pattern to match files.'
                    ),
                    'search_string': types.Schema(
                        type='STRING',
                        description='The string to search for.'
                    )
                },
                required=['pattern', 'search_string']
            )
        )
    ]),
]

# Map function names to implementations
TOOLS_DICT = {
    'fs_tool.list_directory': fs_tool.list_directory,
    'fs_tool.read_file': fs_tool.read_file,
    'fs_tool.write_file': fs_tool.write_file,
    'fs_tool.execute_cli_command': fs_tool.execute_cli_command,
    'fs_tool.search_files': fs_tool.search_files
}

def pretty_print(contents: list[types.Content]) -> str:
    """
    Format content list for readable logging.
    
    Args:
        contents: List of content objects to format
        
    Returns:
        Formatted string representation
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

def manage_token_count(client, contents):
    """
    Ensure contents are within token limits by intelligently pruning when needed.
    
    Args:
        client: Gemini API client
        contents: List of content objects to manage
        
    Returns:
        True if successful, False if pruning failed
    """
    try:
        token_count = client.models.count_tokens(model=MODEL_NAME, contents=contents)
        
        # If within limits, no action needed
        if token_count.total_tokens <= MAX_TOKENS:
            return True
            
        logging.info(f"Token count {token_count.total_tokens} exceeds limit {MAX_TOKENS}, pruning...")
        
        # Keep first item (usually system message) and last N exchanges
        if len(contents) > 3:
            # Keep important context - first message and recent exchanges
            preserve_count = min(5, len(contents) // 2)
            contents[:] = [contents[0]] + contents[-preserve_count:]
            
            # Recheck token count
            token_count = client.models.count_tokens(model=MODEL_NAME, contents=contents)
            logging.info(f"After pruning: {token_count.total_tokens} tokens with {len(contents)} items")
            
            return token_count.total_tokens <= MAX_TOKENS
        
        # If conversation is small but still exceeding, we have a problem
        logging.warning(f"Cannot reduce token count sufficiently: {token_count.total_tokens}")
        return False
        
    except Exception as e:
        logging.error(f"Error managing tokens: {e}")
        return False

def handle_function_call(function_call):
    """
    Process a function call and return its result.
    
    Args:
        function_call: The function call object from Gemini
        
    Returns:
        tuple: (function_response, result_text)
    """
    if function_call.name not in TOOLS_DICT:
        error_msg = f'Missing function: {function_call.name}'
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.error(error_msg)
        return {'error': error_msg}, error_msg
        
    try:
        logging.debug(f"Calling function {function_call.name} with arguments: {function_call.args}")
        result = TOOLS_DICT[function_call.name](**function_call.args)
        print(AnsiColors.TOOL + str(result) + AnsiColors.RESET)
        logging.info(f"Function result: {result}")
        return {'result': result}, str(result)
    except Exception as e:
        error_msg = f"Error in {function_call.name}: {str(e)}"
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.warning(error_msg)
        return {'error': str(e)}, error_msg

def generate_with_tool(prompt, conversation_history=None):
    """
    Generates content using the Gemini model with tools, maintaining conversation history.
    
    Args:
        prompt: User prompt text
        conversation_history: Optional existing conversation history
        
    Returns:
        Updated conversation history
    """
    # Initialize client and conversation history
    client = initialize_client()
    if conversation_history is None:
        conversation_history = []

    # Log and display user prompt
    print(AnsiColors.USER + prompt + AnsiColors.RESET)
    logging.info(f"User prompt: {prompt}")

    # Add the user's prompt to the conversation history
    user_prompt_content = types.Content(
        role='user',
        parts=[types.Part.from_text(text=prompt)]
    )
    conversation_history.append(user_prompt_content)
    contents = conversation_history.copy()

    # Ensure contents are within token limits
    if not manage_token_count(client, contents):
        print(AnsiColors.MODELERROR + "Conversation too large, cannot continue." + AnsiColors.RESET)
        return conversation_history

    # Process generation requests
    try:
        # Set up generation configuration
        generation_config = types.GenerateContentConfig(
            tools=TOOLS,
            system_instruction=SYSTEM,
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
            model=MODEL_NAME,
            contents=contents,
            config=generation_config
        ):
            logging.debug(f"Chunk received: {type(chunk)}")
            
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
                    call_args = str(function_call.args)
                    print(AnsiColors.TOOL + f"{call_name}: {call_args}" + AnsiColors.RESET)
                    logging.info(f"Function call: {call_name} with {call_args}")
                    
                    # Add the function call to request parts
                    request_parts.append(types.Part(function_call=function_call))
                    
                    # Execute the function call
                    function_response, _ = handle_function_call(function_call)
                    
                    # Add the function response to response parts
                    response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=function_call.id,
                                name=function_call.name,
                                response=function_response
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
        
        # If there were function calls, add tool responses to history
        if response_parts:
            tool_response_content = types.Content(
                role='tool',
                parts=response_parts
            )
            conversation_history.append(tool_response_content)
            
            # Continue with function call results
            return generate_with_tool('', conversation_history)
        
        # Output finish information
        print(AnsiColors.MODEL + f"{finish_reason}: {finish_message}" + AnsiColors.RESET)
        logging.info(f"Model finished with reason {finish_reason}: {finish_message}")
    
    except Exception as e:
        error_msg = f"Error during content generation: {e}"
        logging.error(error_msg)
        print(AnsiColors.MODELERROR + "\nError during content generation. See logs for details." + AnsiColors.RESET)
    
    return conversation_history