import os
import argparse

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run AI assistant with different models')
    parser.add_argument('--model', type=str, choices=['claude', 'gemini'], 
                        help='Choose AI model (claude or gemini)')
    args = parser.parse_args()

    # Check which API keys are available
    anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    openai_api_key = os.environ.get('OPENAI_API_KEY')

    # Use command line argument if provided
    if args.model:
        if args.model == 'claude':
            if not anthropic_api_key:
                print("ANTHROPIC_API_KEY is required but not set")
                exit(1)
            print("Using Claude AI model")
            from claude import generate_with_tool
        elif args.model == 'gemini':
            if not gemini_api_key:
                print("GEMINI_API_KEY is required but not set")
                exit(1)
            print("Using Gemini AI model")
            from gemini import generate_with_tool
    else:
        # Select the appropriate AI model based on available API keys (original behavior)
        if anthropic_api_key:
            print("Using Claude AI model")
            from claude import generate_with_tool
        elif gemini_api_key:
            print("Using Gemini AI model")
            from gemini import generate_with_tool
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
        conversation_history = generate_with_tool(user_input, conversation_history)

if __name__ == "__main__":
    main()