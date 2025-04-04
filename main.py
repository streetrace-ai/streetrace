import json
import logging
import os
import argparse
from tools.fs_tool import TOOLS, TOOL_IMPL
from messages import SYSTEM
from colors import AnsiColors

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='generation.log')


def read_system_message():
    """
    Read the system message from a file or return the default message.
    
    Returns:
        str: The system message content
    """
    system_message_path = '.streetrace/system.md'
    if os.path.exists(system_message_path):
        try:
            with open(system_message_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading system message file: {e}")

    # Default system message
    return SYSTEM


def read_project_context():
    """
    Read all project context files from .streetrace directory excluding system.md.
    
    Returns:
        str: Combined content of all context files, or empty string if none exist
    """
    context_files_dir = '.streetrace'
    
    # Check if the directory exists
    if not os.path.exists(context_files_dir) or not os.path.isdir(context_files_dir):
        return ""
        
    # Get all files in the directory excluding system.md
    context_files = [
        os.path.join(context_files_dir, f) for f in os.listdir(context_files_dir)
        if os.path.isfile(os.path.join(context_files_dir, f)) and f != 'system.md'
    ]
    
    # If no context files found, return empty string
    if not context_files:
        return ""
        
    # Read and combine content from all context files
    context_content = []
    for file_path in context_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                file_name = os.path.basename(file_path)
                context_content.append(f"\n\n# Content from {file_name}\n\n{content}\n\n")
        except Exception as e:
            print(f"Error reading context file {file_path}: {e}")
            logging.error(f"Error reading context file {file_path}: {e}")
    
    return "".join(context_content)


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: The parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Run AI assistant with different models')
    parser.add_argument('--engine',
                        type=str,
                        choices=['claude', 'gemini', 'ollama', 'openai'],
                        help='Choose AI engine (claude, gemini, ollama, or openai)')
    parser.add_argument(
        '--model',
        type=str,
        help=
        'Specific model name to use (e.g., claude-3-7-sonnet-20250219, gemini-2.0-flash-001, llama3:8b, or gpt-4-turbo-2024-04-09)'
    )
    parser.add_argument(
        '--prompt',
        type=str,
        help=
        'Prompt to send to the AI model (skips interactive mode if provided)')
    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help=
        'Specify which path to use as the working directory for all file operations'
    )
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
    # For Ollama, we don't need an API key, but we can check for the base URL
    ollama_url = os.environ.get('OLLAMA_API_URL')

    # Default model names
    claude_model_name = "claude-3-7-sonnet-20250219"
    gemini_model_name = "gemini-2.0-flash-001"
    ollama_model_name = "llama3:8b"
    openai_model_name = "gpt-4-turbo-2024-04-09"

    # Override default model name if provided through command line
    if args.model:
        if args.engine == 'claude':
            claude_model_name = args.model
        elif args.engine == 'gemini':
            gemini_model_name = args.model
        elif args.engine == 'ollama':
            ollama_model_name = args.model
        elif args.engine == 'openai':
            openai_model_name = args.model
        else:
            print(
                f"Model name '{args.model}' provided but no engine type (--engine) specified"
            )
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
        elif args.engine == 'ollama':
            print(f"Using Ollama AI engine: {ollama_model_name}")
            print(f"Ollama API URL: {ollama_url or 'http://localhost:11434 (default)'}")
            from ollama_client import generate_with_tool
            model_name = ollama_model_name
        elif args.engine == 'openai':
            if not openai_api_key:
                print("OPENAI_API_KEY is required but not set")
                exit(1)
            print(f"Using OpenAI engine: {openai_model_name}")
            from openai_client import generate_with_tool
            model_name = openai_model_name
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
            print(f"Using OpenAI model: {openai_model_name}")
            from openai_client import generate_with_tool
            model_name = openai_model_name
        elif ollama_url or os.path.exists('/usr/bin/ollama') or os.path.exists('/usr/local/bin/ollama'):
            print(f"Using Ollama AI model: {ollama_model_name}")
            from ollama_client import generate_with_tool
            model_name = ollama_model_name
        else:
            print(
                "No API keys found. Please set one of the following environment variables:"
            )
            print("- ANTHROPIC_API_KEY for Claude")
            print("- GEMINI_API_KEY for Gemini")
            print("- OPENAI_API_KEY for OpenAI")
            print("- OLLAMA_API_URL for Ollama (optional, defaults to http://localhost:11434)")
            exit(1)

    return generate_with_tool, model_name


def call_tool(tool_name, args, original_call, work_dir):
    """
    Call the appropriate tool function based on the tool name.
    
    Args:
        tool_name: Name of the tool to call
        args: Dictionary of arguments to pass to the function
        original_call: The original function call object from the model
        work_dir: Path to use as the working directory for file operations
        
    Returns:
        tuple: (function_response, result_text)
    """
    logging.debug(f"Calling tool {tool_name} with arguments: {args}")
    if tool_name in TOOL_IMPL:
        tool = TOOL_IMPL[tool_name]
        if 'work_dir' in tool.__code__.co_varnames:
            args = { **args, 'work_dir': work_dir }
        try:
            result = tool(**args)
            print(AnsiColors.TOOL + str(result) + AnsiColors.RESET)
            logging.info(f"Function result: {result}")
            return {"success": True, "result": json.dumps(result)}
        except Exception as e:
            error_msg = f"Error in {tool_name}: {str(e)}"
            print(AnsiColors.TOOLERROR + error_msg + AnsiColors.RESET)
            logging.warning(error_msg)
            return {"error": str(e)}
    else:
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
    
    # Read project context from .streetrace files
    project_context = read_project_context()

    # Initialize conversation history
    conversation_history = []

    # Get the working directory path
    working_dir = args.path if args.path else os.getcwd()
    if working_dir:
        print(f"Using working directory: {working_dir}")

    def call_tool_f(tool_name, args, original_call):
        return call_tool(tool_name, args, original_call, working_dir)

    # Non-interactive mode with --prompt argument
    if args.prompt:
        print(f"Running in non-interactive mode with prompt: {args.prompt}")
        
        # Use the prompt directly without modifying it
        if project_context:
            print("Adding project context to conversation")
            
        generate_with_tool(args.prompt, TOOLS, call_tool_f,
                           conversation_history, model_name, system_message, project_context)
        return

    # Interactive mode
    print("Starting interactive session. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
            
        # Pass project_context as a separate parameter only on the first interaction
        if not conversation_history:
            if project_context:
                print("Adding project context to conversation")
            conversation_history = generate_with_tool(
                user_input, TOOLS, call_tool_f, conversation_history, 
                model_name, system_message, project_context
            )
        else:
            # For subsequent interactions, don't pass project_context
            conversation_history = generate_with_tool(
                user_input, TOOLS, call_tool_f, conversation_history, 
                model_name, system_message
            )


if __name__ == "__main__":
    main()