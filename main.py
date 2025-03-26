from gemini import generate_with_tool

# Example usage:
conversation_history = []
while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        break
    conversation_history = generate_with_tool(user_input, conversation_history)
