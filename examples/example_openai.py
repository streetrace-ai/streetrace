"""
Example of using OpenAI integration directly, without the command line interface.
This demonstrates how to use the generate_with_tool function programmatically.
"""

import os
import sys
import logging

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai_client import generate_with_tool
from tools.fs_tool import TOOLS

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Define a custom system message
system_message = """You are a helpful AI assistant specializing in Python development.
You provide clear, concise explanations and write clean, well-documented code."""

def call_tool(tool_name, args, original_call):
    """
    Wrapper function for calling tools.
    
    Args:
        tool_name (str): Name of the tool to call
        args (dict): Arguments for the tool
        original_call: Original call object from the model
        
    Returns:
        The result from the tool
    """
    working_dir = os.getcwd()
    
    try:
        for tool in TOOLS:
            if tool['name'] == tool_name:
                if 'work_dir' in tool['function'].__code__.co_varnames:
                    result = tool['function'](**{**args, 'work_dir': working_dir})
                else:
                    result = tool['function'](**args)
                return result
                
    except Exception as e:
        error_msg = f"Error in {tool_name}: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {"error": str(e)}
    
    print(f"Tool not found: {tool_name}")
    return {"error": f"Tool not found: {tool_name}"}

def main():
    """
    Main function that demonstrates how to use the OpenAI integration
    programmatically with a custom system message.
    """
    # Check if OpenAI API key is set
    if not os.environ.get('OPENAI_API_KEY'):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set it with: export OPENAI_API_KEY=your_api_key_here")
        sys.exit(1)
    
    # Define the prompt
    prompt = "Create a simple Python function to calculate the factorial of a number."
    
    # Model name (optional, uses default if not specified)
    model_name = "gpt-4-turbo-2024-04-09"  # Use a specific model
    
    # Call the generate_with_tool function with our custom system message
    conversation_history = generate_with_tool(
        prompt=prompt,
        tools=TOOLS,
        call_tool=call_tool,
        model_name=model_name,
        system_message=system_message
    )
    
    # If you want to continue the conversation, you can use the updated conversation history
    # For this example, we'll just print the number of messages in the conversation
    print(f"\nConversation history contains {len(conversation_history)} messages.")
    
    # Example of continuing the conversation (commented out)
    # follow_up_prompt = "Now modify the factorial function to handle negative numbers gracefully."
    # conversation_history = generate_with_tool(
    #     prompt=follow_up_prompt,
    #     tools=TOOLS,
    #     call_tool=call_tool,
    #     conversation_history=conversation_history,
    #     model_name=model_name,
    #     system_message=system_message
    # )

if __name__ == "__main__":
    main()