# Hello World Agent

A simple example agent that demonstrates the StreetRaceAgent interface.

## Capabilities

- Greets the user in a friendly manner
- Lists files in the current directory
- Reads file contents when requested

## Usage

This agent can be used with the `run_agent` tool:

```python
run_agent(agent_name="Hello World", input_text="Hi, please list the files in my directory.")
```

Or directly through the AgentManager:

```python
async with agent_manager.create_agent("Hello World") as agent:
    # Use the agent
```

## Implementation

The Hello World agent implements the `StreetRaceAgent` interface, which requires:

1. `get_agent_card()` - Provides metadata about the agent
2. `get_required_tools()` - Lists the tools needed by the agent
3. `create_agent()` - Creates the actual agent instance

It also provides a legacy implementation through the `get_agent_metadata()` and `run_agent()` functions for backward compatibility.

## Development

This agent serves as a template for creating new agents. You can copy this directory and modify it to create your own agents.