# StreetRace🚗💨 Components Overview

## ./workflow/supervisor.py

Orchestrates the interaction loop between users and AI agents, forming the core workflow engine of StreetRace.

The Supervisor class manages the complete execution lifecycle of AI agent interactions:

1. **Session Management**: Creates and maintains ADK (Agent Development Kit) sessions, persisting conversation context between interactions using the JSONSessionService.

2. **Agent Creation**: Dynamically instantiates AI agents with appropriate tools and system context, configuring them for file operations and CLI command execution.

3. **Event Processing**: Handles events from Google ADK's Runner execution flow, rendering UI updates and capturing responses to maintain conversation continuity.

4. **Tool Integration**: Connects agents to system tools through ToolProvider, enabling file system operations, CLI command execution, and other capabilities required for coding assistance.

5. **History Management**: Maintains both session-specific state for ADK's context and global conversational history through HistoryManager for long-term memory across sessions.

The implementation follows a clear separation between:

- Session state (managed via ADK's Session objects) for tracking immediate interaction context
- Global history (managed via HistoryManager) for maintaining project-wide knowledge
- Tools (provided by ToolProvider) for enabling agent capabilities on the local system

Key architectural components and dependencies:

- `google.adk.Runner` for executing agent logic and handling event processing
- `google.adk.agents.Agent` for building the agent with appropriate configuration
- `google.adk.sessions` interfaces for managing conversation state
- `ToolProvider` for supplying file system and CLI capabilities
- `BaseSessionService` implementation for persisting sessions between interactions
- `LlmInterface` for interacting with language models through standardized interfaces

The Supervisor is instantiated in `app.py` and serves as the core execution engine that processes each user prompt, manages agent responses, and handles the persistence of conversation state.
