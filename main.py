import logging
import os
import argparse
from tools.fs_tool import TOOLS
from messages import SYSTEM
from colors import AnsiColors

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='generation.log'
)


def read_system_message():
    """
    Read the system message from a file or return the default message.
    
    Returns:
        str: The system message content
    """
    system_message_path = '.streetrace/system_message.txt'
    if os.path.exists(system_message_path):
        try:
            with open(system_message_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading system message file: {e}")
    
    # Default system message
    return SYSTEM

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: The parsed arguments
    """
    parser = argparse.ArgumentParser(description='Run AI assistant with different models')
    parser.add_argument('--engine', type=str, choices=['claude', 'gemini'], 
                        help='Choose AI engine (claude or gemini)')
    parser.add_argument('--model', type=str,
                        help='Specific model name to use (e.g., claude-3-7-sonnet-20250219 or gemini-2.0-flash-001)')
    parser.add_argument('--prompt', type=str,
                        help='Prompt to send to the AI model (skips interactive mode if provided)')
    return parser.parse_args()

def setup_model(args):
    """
    Set up the appropriate AI engine based on arguments and available API keys.
    
    Args:
        args: Command line arguments
        
    Returns:
        tuple: (generate_with_tool function, model_name to use)
    """
    # Check which API keys are available
    anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    openai_api_key = os.environ.get('OPENAI_API_KEY')

    # Default model names
    claude_model_name = "claude-3-7-sonnet-20250219"
    gemini_model_name = "gemini-2.0-flash-001"
    
    # Override default model name if provided through command line
    if args.model:
        if args.engine == 'claude':
            claude_model_name = args.model
        elif args.engine == 'gemini':
            gemini_model_name = args.model
        else:
            print(f"Model name '{args.model}' provided but no engine type (--engine) specified")
            exit(1)

    # Use command line argument if provided
    if args.engine:
        if args.engine == 'claude':
            if not anthropic_api_key:
                print("ANTHROPIC_API_KEY is required but not set")
                exit(1)
            print(f"Using Claude AI engine: {claude_model_name}")
            from claude import generate_with_tool
            model_name = claude_model_name
        elif args.engine == 'gemini':
            if not gemini_api_key:
                print("GEMINI_API_KEY is required but not set")
                exit(1)
            print(f"Using Gemini AI engine: {gemini_model_name}")
            from gemini import generate_with_tool
            model_name = gemini_model_name
    else:
        # Select the appropriate AI model based on available API keys (original behavior)
        if anthropic_api_key:
            print(f"Using Claude AI model: {claude_model_name}")
            from claude import generate_with_tool
            model_name = claude_model_name
        elif gemini_api_key:
            print(f"Using Gemini AI model: {gemini_model_name}")
            from gemini import generate_with_tool
            model_name = gemini_model_name
        elif openai_api_key:
            print("OpenAI integration is not implemented yet")
            exit(1)
        else:
            print("No API keys found. Please set one of the following environment variables:")
            print("- ANTHROPIC_API_KEY for Claude")
            print("- GEMINI_API_KEY for Gemini")
            print("- OPENAI_API_KEY for OpenAI (not implemented yet)")
            exit(1)
            
    return generate_with_tool, model_name

    
def call_tool(tool_name, args, original_call):
    """
    Call the appropriate tool function based on the tool name.
    
    Args:
        tool_name: Name of the tool to call
        args: Dictionary of arguments to pass to the function
        original_call: The original function call object from the model
        
    Returns:
        tuple: (function_response, result_text)
    """
    logging.debug(f"Calling tool {tool_name} with arguments: {args}")
    try:
        for tool in TOOLS:
            if tool['name'] == tool_name:
                result = tool['function'](**args)
                print(AnsiColors.TOOL + str(result) + AnsiColors.RESET)
                logging.info(f"Function result: {result}")
                return {"result": result}
    except Exception as e:
        error_msg = f"Error in {tool_name.name}: {str(e)}"
        print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
        logging.warning(error_msg)
        return {"error": str(e)}
    
    
    error_msg = f"Tool not found: {tool_name}"
    print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
    logging.error(error_msg)
    return {'error': error_msg}

def main():
    """Main entry point for the application"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up the appropriate AI model
    generate_with_tool, model_name = setup_model(args)

    # Read the system message
    system_message = read_system_message()

    # Initialize conversation history
    conversation_history = []
    
    # Non-interactive mode with --prompt argument
    if args.prompt:
        print(f"Running in non-interactive mode with prompt: {args.prompt}")
        generate_with_tool(args.prompt, TOOLS, call_tool, conversation_history, model_name, system_message)
        return
    
    # Interactive mode
    print("Starting interactive session. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        conversation_history = generate_with_tool(user_input, TOOLS, call_tool, conversation_history, model_name, system_message)

if __name__ == "__main__":
    main()