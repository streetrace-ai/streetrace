# Agent Loader Tests

This directory contains unit tests for the `streetrace.agents.agent_loader` module, which is responsible for discovering, validating, and loading agent implementations.

## Test Structure

The tests are organized into several files:

- `test_agent_loader.py`: Tests for the core functionality of the agent loader including module importing, agent class detection, validation, and retrieval.
- `test_agent_info.py`: Tests for the `AgentInfo` class that holds agent card and module references.
- `test_non_directory_item.py`: A focused test to ensure non-directory items are properly handled during agent discovery.
- `test_agent_loader_filesystem.py`: Integration tests that work with a simulated file system (currently skipped by default).

## Fixtures

- `fixtures/`: Contains utilities for setting up test environments.
- `fixtures/fixture_generator.py`: A utility for generating temporary agent directories for testing.
- `conftest.py`: Contains shared pytest fixtures for the agent loader tests.

## Coverage

These tests aim to provide 100% code coverage for the agent loader module, ensuring that all code paths are tested, including error handling and edge cases.

## Running the Tests

You can run these tests using:

```bash
# Run all agent loader tests
poetry run pytest tests/unit/agents/agent_loader

# Run with coverage
poetry run coverage run --source=streetrace.agents.agent_loader -m pytest tests/unit/agents/agent_loader
poetry run coverage report
```