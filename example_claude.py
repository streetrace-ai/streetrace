#!/usr/bin/env python3
"""
Example usage of the claude.py module.
This script demonstrates how to interact with Claude 3 Sonnet using the generate_with_tool function.
"""

from claude import generate_with_tool

def main():
    """
    Main function that demonstrates a conversation with Claude.
    """
    print("Starting a conversation with Claude...")
    
    # Start a new conversation - first request
    conversation_history = generate_with_tool(
        "List the Python files in the current directory and give me a short summary of what each one does."
    )
    
    # Continue the conversation - follow-up request
    conversation_history = generate_with_tool(
        "Now, let's create a simple 'hello world' Python script called hello.py.",
        conversation_history
    )
    
    # Another follow-up request
    conversation_history = generate_with_tool(
        "Modify hello.py to accept a command-line argument for the name to greet.",
        conversation_history
    )
    
    print("\nConversation completed.")

if __name__ == "__main__":
    main()