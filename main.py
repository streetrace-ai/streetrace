import os
import argparse

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run AI assistant with different models')
    parser.add_argument('--model', type=str, choices=['claude', 'gemini'], 
                        help='Choose AI model (claude or gemini)')
    parser.add_argument('--model-name', type=str,
                        help='Specific model name to use (e.g., claude-3-7-sonnet-20250219 or gemini-2.0-flash-001)')
    args = parser.parse_args()

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

    # Example usage:
    conversation_history = []
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        conversation_history = generate_with_tool(user_input, conversation_history, model_name)

if __name__ == "__main__":
    main()