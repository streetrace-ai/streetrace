"""Hello World Agent implementation.

A simple example agent that demonstrates the basic structure of a StreetRace agent.
"""

from typing import Any


def get_agent_metadata() -> dict[str, str]:
    """Return metadata about this agent.

    Returns:
        Dictionary containing agent metadata with name and description

    """
    return {
        "name": "Hello World",
        "description": "A simple example agent that greets the user and demonstrates the basic agent structure.",
    }


def run_agent(input_text: str) -> dict[str, Any]:
    """Run the Hello World agent with the provided input.

    Args:
        input_text: The text input from the user

    Returns:
        A dictionary containing the agent's response

    """
    # This is just a stub implementation
    return {
        "status": "success",
        "response": f"👋 Hello! You said: '{input_text}'. I'm a simple example agent.",
        "metadata": {
            "agent_name": "Hello World",
            "version": "1.0.0",
        },
    }


if __name__ == "__main__":
    # This allows the agent to be run directly for testing
    test_input = "Testing the Hello World agent"
    result = run_agent(test_input)
    print(result["response"])
