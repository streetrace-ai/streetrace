# Hello World Agent

This is a simple example agent that demonstrates the basic structure required for a StreetRace agent. It responds to user input with a greeting message that includes the input text.

## Features

- Demonstrates the required agent interface
- Shows proper metadata structure
- Includes a simple input/output pattern

## Usage

This agent can be run directly or through the StreetRace agent system:

```python
from agents.hello_world.agent import run_agent

result = run_agent("Hello agent!")
print(result["response"])
```

## Development

This agent serves as a template for developing more complex agents. Use it as a starting point for your own custom agents.