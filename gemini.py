import os
import logging
from google import genai
from google.genai import types

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


def transform_tools_to_gemini_format(tools):
    """
    Transform tools from common format to Gemini-specific format.
    
    Args:
        tools (list): List of tool definitions in common format
        
    Returns:
        list: List of tool definitions in Gemini format
    """
    gemini_tools = []
    tools_dict = {tool['name']: tool['function'] for tool in tools}
    
    for tool in tools:
        # Convert properties to Gemini Schema format
        gemini_properties = {}
        for param_name, param_def in tool['parameters']['properties'].items():
            gemini_properties[param_name] = types.Schema(
                type=param_def['type'].upper(),  # Gemini uses uppercase type names
                description=param_def['description']
            )
        
        # Create the function declaration
        function_declaration = types.FunctionDeclaration(
            name=tool['name'],
            description=tool['description'],
            parameters=types.Schema(
                type='OBJECT',
                properties=gemini_properties,
                required=tool['parameters']['required']
            )
        )
        
        # Add the tool to the list
        gemini_tools.append(types.Tool(function_declarations=[function_declaration]))
    
    return gemini_tools, tools_dict

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

def manage_token_count(client, contents, model_name):
    """
    Ensure contents are within token limits by intelligently pruning when needed.
    
    Args:
        client: Gemini API client
        contents: List of content objects to manage
        
    Returns:
        True if successful, False if pruning failed
    """
    try:
        token_count = client.models.count_tokens(model=model_name, contents=contents)
        
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
            token_count = client.models.count_tokens(model=model_name, contents=contents)
            logging.info(f"After pruning: {token_count.total_tokens} tokens with {len(contents)} items")
            
            return token_count.total_tokens <= MAX_TOKENS
        
        # If conversation is small but still exceeding, we have a problem
        logging.warning(f"Cannot reduce token count sufficiently: {token_count.total_tokens}")
        return False
        
    except Exception as e:
        logging.error(f"Error managing tokens: {e}")
        return False

def handle_function_call(function_call, tools_dict):
    """
    Process a function call and return its result.
    
    Args:
        function_call: The function call object from Gemini
        
    Returns:
        tuple: (function_response, result_text)
    """
    if function_call.name not in tools_dict:
        error_msg = f'Missing function: {function_call.name}'
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.error(error_msg)
        return {'error': error_msg}, error_msg
        
    try:
        logging.debug(f"Calling function {function_call.name} with arguments: {function_call.args}")
        result = tools_dict[function_call.name](**function_call.args)
        print(AnsiColors.TOOL + str(result) + AnsiColors.RESET)
        logging.info(f"Function result: {result}")
        return {'result': result}, str(result)
    except Exception as e:
        error_msg = f"Error in {function_call.name}: {str(e)}"
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.warning(error_msg)
        return {'error': str(e)}, error_msg

def generate_with_tool(prompt, tools, conversation_history=None, model_name=MODEL_NAME, system_message=None):
    """
    Generates content using the Gemini model with the custom tool,
    maintaining conversation history.
    
    Args:
        prompt (str): The user's input prompt
        tools (list): List of tool definitions in common format.
        conversation_history (list, optional): The history of the conversation. Defaults to None.
        model_name (str, optional): The name of the Gemini model to use. Defaults to "gemini-2.0-flash-001".
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

    # Transform tools to Gemini format if provided, otherwise use default
    gemini_tools, tools_dict = transform_tools_to_gemini_format(tools)

    if prompt:
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
    if not manage_token_count(client, contents, model_name):
        print(AnsiColors.MODELERROR + "Conversation too large, cannot continue." + AnsiColors.RESET)
        return conversation_history

    # Process generation requests
    try:
        # Set up generation configuration
        generation_config = types.GenerateContentConfig(
            tools=gemini_tools,
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
                    function_response, _ = handle_function_call(function_call, tools_dict)
                    
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
            return generate_with_tool('', tools, conversation_history, model_name, system_message)
        
        # Output finish information
        print("\n" + AnsiColors.MODEL + f"{finish_reason}: {finish_message}" + AnsiColors.RESET)
        logging.info(f"Model finished with reason {finish_reason}: {finish_message}")
    
    except Exception as e:
        error_msg = f"Error during content generation: {e}"
        logging.error(error_msg)
        print(AnsiColors.MODELERROR + "\nError during content generation. See logs for details." + AnsiColors.RESET)
    
    return conversation_history