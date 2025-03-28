import os
import argparse

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
    return """You are an experienced software engineer implementing code for a project working as a peer engineer
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
Remember, never commit the changes."""

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: The parsed arguments
    """
    parser = argparse.ArgumentParser(description='Run AI assistant with different models')
    parser.add_argument('--model', type=str, choices=['claude', 'gemini'], 
                        help='Choose AI model (claude or gemini)')
    parser.add_argument('--model-name', type=str,
                        help='Specific model name to use (e.g., claude-3-7-sonnet-20250219 or gemini-2.0-flash-001)')
    parser.add_argument('--prompt', type=str,
                        help='Prompt to send to the AI model (skips interactive mode if provided)')
    return parser.parse_args()

def setup_model(args):
    """
    Set up the appropriate AI model based on arguments and available API keys.
    
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
    if args.model_name:
        if args.model == 'claude':
            claude_model_name = args.model_name
        elif args.model == 'gemini':
            gemini_model_name = args.model_name
        else:
            print(f"Model name '{args.model_name}' provided but no model type (--model) specified")
            exit(1)

    # Use command line argument if provided
    if args.model:
        if args.model == 'claude':
            if not anthropic_api_key:
                print("ANTHROPIC_API_KEY is required but not set")
                exit(1)
            print(f"Using Claude AI model: {claude_model_name}")
            from claude import generate_with_tool
            model_name = claude_model_name
        elif args.model == 'gemini':
            if not gemini_api_key:
                print("GEMINI_API_KEY is required but not set")
                exit(1)
            print(f"Using Gemini AI model: {gemini_model_name}")
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
        generate_with_tool(args.prompt, conversation_history, model_name, system_message)
        return
    
    # Interactive mode
    print("Starting interactive session. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        conversation_history = generate_with_tool(user_input, conversation_history, model_name, system_message)

if __name__ == "__main__":
    main()