#!/usr/bin/env python3
"""
Example usage of the gemini.py module.
This script demonstrates how to interact with Gemini using the generate_with_tool function.
"""

from gemini import generate_with_tool

def main():
    """
    Main function that demonstrates a conversation with Gemini.
    """
    print("Starting a conversation with Gemini...")
    
    # Define a custom system message
    system_message = """You are a helpful AI assistant specializing in Python development.
You provide clear, concise explanations and write clean, well-documented code.
When asked to create or modify code, you ensure it follows PEP 8 style guidelines.
"""
    
    # Start a new conversation with custom system message
    conversation_history = generate_with_tool(
        "List the Python files in the current directory and give me a short summary of what each one does.",
        system_message=system_message
    )
    
    # Continue the conversation - follow-up request (system message persists through the conversation)
    conversation_history = generate_with_tool(
        "Now, let's create a simple 'hello world' Python script called hello.py.",
        conversation_history,
        system_message=system_message
    )
    
    # Another follow-up request
    conversation_history = generate_with_tool(
        "Modify hello.py to accept a command-line argument for the name to greet.",
        conversation_history,
        system_message=system_message
    )
    
    print("\nConversation completed.")

if __name__ == "__main__":
    main()