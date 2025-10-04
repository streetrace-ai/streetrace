# Using Tools with Streetrace

**Target Audience:** Senior Engineers  
**Version:** 1.0  
**Last Updated:** 2025-08-20

## Table of Contents

1. [Overview](#overview)
2. [Tool Architecture](#tool-architecture)
3. [Tool Types](#tool-types)
4. [Adding Tools to Agents](#adding-tools-to-agents)
5. [Streetrace Internal Tools](#streetrace-internal-tools)
6. [Model Context Protocol (MCP) Tools](#model-context-protocol-mcp-tools)
7. [Callable Tools](#callable-tools)
8. [Tool Configuration Examples](#tool-configuration-examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Patterns](#advanced-patterns)

## Overview

Streetrace provides a powerful and extensible tool system that allows AI agents to interact with external systems, execute commands, and access various services. This manual covers how to configure, add, and manage tools for both Python-based agents and YAML-based agents.

The tool system is built around three core concepts:
- **Tool References**: Structured descriptions of tools that agents need
- **Tool Provider**: Centralized tool management and lifecycle handling
- **Tool Types**: Different categories of tools (Streetrace internal, MCP, callable)

## Tool Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│     Agent       │───▶│   Tool Provider  │───▶│  Tool Instance │
│  (requires      │    │  (manages        │    │  (ADK Tool/    │
│   tools)        │    │   lifecycle)     │    │   Function)    │
└─────────────────┘    └──────────────────┘    └────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Tool Reference │    │  Tool Factory    │    │ External System│
│  (structured    │    │  (creates        │    │ (filesystem,   │
│   config)       │    │   instances)     │    │  MCP server)   │
└─────────────────┘    └──────────────────┘    └────────────────┘
```

## Tool Types

Streetrace supports three types of tools:

### 1. Streetrace Internal Tools
- **Purpose**: Built-in tools for common operations (file I/O, CLI commands)
- **Performance**: Fastest, no external dependencies
- **Use Case**: Core functionality every agent needs

### 2. Model Context Protocol (MCP) Tools
- **Purpose**: External services via standardized protocol
- **Performance**: Network-dependent, feature-rich
- **Use Case**: Specialized services (GitHub, databases, APIs)

### 3. Callable Tools
- **Purpose**: Direct Python function calls
- **Performance**: Fast, inline execution
- **Use Case**: Custom business logic, utility functions

## Adding Tools to Agents

### For Python Agents

Tools are defined in the `get_required_tools()` method using structured `ToolRef` objects:

```python
from streetrace.tools.tool_refs import (
    McpToolRef,
    StreetraceToolRef,
    CallableToolRef,
)
from streetrace.tools.mcp_transport import StdioTransport, HttpTransport

class MyAgent(StreetRaceAgent):
    async def get_required_tools(self) -> list[AnyTool]:
        return [
            # Streetrace internal tools
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
            
            # MCP tools
            McpToolRef(
                name="filesystem",
                server=StdioTransport(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem"]
                ),
                tools=["edit_file", "move_file"]
            ),
            
            # Callable tools
            CallableToolRef(import_path="mymodule.utils:helper_function")
        ]
```

### For YAML Agents

Tools are defined in the `tools` section of the YAML specification:

```yaml
version: 1
kind: agent
name: my_agent
description: Example agent with various tools
tools:
  # Streetrace internal tools
  - streetrace:
      module: fs_tool
      function: read_file
  - streetrace:
      module: cli_tool
      function: execute_cli_command
  
  # MCP tools
  - mcp:
      name: filesystem
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem"]
      tools: ["edit_file", "move_file"]
  
  - mcp:
      name: github
      server:
        type: http
        url: "https://api.githubcopilot.com/mcp/"
        headers:
          Authorization: "Bearer ${GITHUB_PAT}"
        timeout: 10
```

## Streetrace Internal Tools

Streetrace provides a comprehensive set of built-in tools optimized for common development tasks.

### File System Tools (`fs_tool` module)

| Function | Description | Use Case |
|----------|-------------|----------|
| `read_file` | Read file contents with encoding detection | Reading source code, configs |
| `write_file` | Write content to files with safety checks | Creating/updating files |
| `append_to_file` | Append content to existing files | Logging, incremental updates |
| `list_directory` | List directory contents with filtering | Project exploration |
| `create_directory` | Create directories with parent creation | Project structure setup |
| `find_in_files` | Search for patterns across files | Code analysis, refactoring |

**Example Usage:**
```python
# Python agent
StreetraceToolRef(module="fs_tool", function="read_file"),
StreetraceToolRef(module="fs_tool", function="write_file"),
```

```yaml
# YAML agent
tools:
  - streetrace:
      module: fs_tool
      function: read_file
  - streetrace:
      module: fs_tool
      function: write_file
```

### CLI Tools (`cli_tool` module)

| Function | Description | Use Case |
|----------|-------------|----------|
| `execute_cli_command` | Execute shell commands with safety checks | Build processes, git operations |

**Safety Features:**
- Command analysis for risky operations
- Path validation and containment
- Resource usage monitoring
- Configurable allow/deny lists

**Example Usage:**
```python
# Python agent
StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
```

```yaml
# YAML agent
tools:
  - streetrace:
      module: cli_tool
      function: execute_cli_command
```

### Agent Management Tools (`agent_tools` module)

| Function | Description | Use Case |
|----------|-------------|----------|
| `list_agents` | List available agents in the system | Agent discovery |

## Model Context Protocol (MCP) Tools

MCP tools connect to external services using standardized protocols. Streetrace supports three transport types:

### STDIO Transport
For local command-line MCP servers:

```python
# Python
McpToolRef(
    name="filesystem",
    server=StdioTransport(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        env={"CUSTOM_VAR": "value"}  # Optional environment variables
    ),
    tools=["edit_file", "move_file", "get_file_info"]
)
```

```yaml
# YAML
- mcp:
    name: filesystem
    server:
      type: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem"]
      env:
        CUSTOM_VAR: value
    tools: ["edit_file", "move_file", "get_file_info"]
```

### HTTP Transport
For HTTP-based MCP servers:

```python
# Python
McpToolRef(
    name="github",
    server=HttpTransport(
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    ),
    tools=[]  # Empty list means all available tools
)
```

```yaml
# YAML
- mcp:
    name: github
    server:
      type: http
      url: "https://api.githubcopilot.com/mcp/"
      headers:
        Authorization: "Bearer ${GITHUB_PAT}"
      timeout: 10
    tools: []  # All available tools
```

### SSE Transport
For Server-Sent Events MCP servers:

```python
# Python
McpToolRef(
    name="realtime_data",
    server=SseTransport(
        url="https://api.example.com/mcp/sse",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
)
```

```yaml
# YAML
- mcp:
    name: realtime_data
    server:
      type: sse
      url: "https://api.example.com/mcp/sse"
      headers:
        Authorization: "Bearer ${API_TOKEN}"
      timeout: 30
```

### Common MCP Servers

| Server | Purpose | Transport | Example Tools |
|--------|---------|-----------|---------------|
| `@modelcontextprotocol/server-filesystem` | File operations | STDIO | `edit_file`, `move_file`, `get_file_info` |
| `@modelcontextprotocol/server-sqlite` | Database operations | STDIO | `query`, `schema`, `list_tables` |
| `@modelcontextprotocol/server-git` | Git operations | STDIO | `commit`, `push`, `branch`, `log` |
| GitHub Copilot MCP | GitHub integration | HTTP | `create_issue`, `list_repos`, `search_code` |
| Context7 MCP | Documentation lookup | HTTP | `search_docs`, `get_examples` |

## Callable Tools

For direct Python function calls:

```python
# Python agent
CallableToolRef(import_path="myproject.utils:validate_config"),
CallableToolRef(import_path="myproject.database:run_migration"),
```

```yaml
# YAML agent - not supported yet
# Callable tools are only available in Python agents currently
```

The function must be importable and follow this signature:
```python
def my_tool_function(*args, **kwargs) -> Any:
    """Tool function implementation."""
    # Your logic here
    return result
```

## Tool Configuration Examples

### Complete Python Agent Example

```python
"""Example agent with comprehensive tool configuration."""

import os
from typing import override
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef
from streetrace.tools.mcp_transport import HttpTransport, StdioTransport

class DeveloperAgent(StreetRaceAgent):
    @override
    async def get_required_tools(self) -> list[AnyTool]:
        return [
            # Core file operations
            StreetraceToolRef(module="fs_tool", function="read_file"),
            StreetraceToolRef(module="fs_tool", function="write_file"),
            StreetraceToolRef(module="fs_tool", function="list_directory"),
            StreetraceToolRef(module="fs_tool", function="find_in_files"),
            
            # Command execution
            StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
            
            # Advanced file operations via MCP
            McpToolRef(
                name="filesystem",
                server=StdioTransport(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem"]
                ),
                tools=["edit_file", "move_file", "get_file_info"]
            ),
            
            # Git operations
            McpToolRef(
                name="git",
                server=StdioTransport(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-git"]
                ),
                tools=["commit", "push", "log", "status"]
            ),
            
            # GitHub integration (requires GITHUB_PAT environment variable)
            McpToolRef(
                name="github",
                server=HttpTransport(
                    url="https://api.githubcopilot.com/mcp/",
                    headers={
                        "Authorization": f"Bearer {os.environ.get('GITHUB_PAT')}"
                    },
                    timeout=10
                )
            ),
            
            # Documentation lookup
            McpToolRef(
                name="context7",
                server=HttpTransport(
                    url="https://mcp.context7.com/mcp",
                    timeout=10
                )
            ),
        ]
```

### Complete YAML Agent Example

```yaml
version: 1
kind: agent
name: full_stack_developer
description: Full-stack development agent with comprehensive tooling
model: claude-3-5-sonnet-20241022

instruction: |
  You are a senior full-stack developer with access to comprehensive development tools.
  Use file operations for code changes, CLI tools for builds and tests, GitHub tools for
  repository management, and documentation tools for research.

tools:
  # Core file system operations
  - streetrace:
      module: fs_tool
      function: read_file
  - streetrace:
      module: fs_tool
      function: write_file
  - streetrace:
      module: fs_tool
      function: list_directory
  - streetrace:
      module: fs_tool
      function: find_in_files
  - streetrace:
      module: fs_tool
      function: create_directory
  - streetrace:
      module: fs_tool
      function: append_to_file

  # Command execution
  - streetrace:
      module: cli_tool
      function: execute_cli_command

  # Advanced file operations
  - mcp:
      name: filesystem
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-filesystem"]
      tools: ["edit_file", "move_file", "get_file_info", "list_allowed_directories"]

  # Git version control
  - mcp:
      name: git
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-git"]
      tools: ["commit", "push", "pull", "status", "log", "branch", "diff"]

  # GitHub integration (requires GITHUB_PAT environment variable)
  - mcp:
      name: github
      server:
        type: http
        url: "https://api.githubcopilot.com/mcp/"
        headers:
          Authorization: "Bearer ${GITHUB_PAT}"
        timeout: 15

  # Database operations (SQLite)
  - mcp:
      name: database
      server:
        type: stdio
        command: npx
        args: ["-y", "@modelcontextprotocol/server-sqlite"]
        env:
          DATABASE_PATH: "${DATABASE_PATH:-./app.db}"
      tools: ["query", "schema", "list_tables", "describe_table"]

  # Documentation and API lookup
  - mcp:
      name: context7
      server:
        type: http
        url: "https://mcp.context7.com/mcp"
        timeout: 10

adk:
  # ADK-specific configuration
  disallow_transfer_to_parent: false
  include_contents: "default"
```

## Best Practices

### 1. Tool Selection Strategy

**Start Minimal:**
```python
# Begin with essential tools only
tools = [
    StreetraceToolRef(module="fs_tool", function="read_file"),
    StreetraceToolRef(module="fs_tool", function="write_file"),
    StreetraceToolRef(module="cli_tool", function="execute_cli_command"),
]
```

**Scale Gradually:**
```python
# Add specialized tools as needed
if requires_github_integration:
    tools.append(McpToolRef(name="github", server=github_server))

if requires_database_access:
    tools.append(McpToolRef(name="sqlite", server=sqlite_server))
```

### 2. Environment Variable Management

**YAML Environment Variables:**
```yaml
# Use environment variable expansion for sensitive data
server:
  type: http
  url: "${API_URL}"
  headers:
    Authorization: "Bearer ${API_TOKEN}"
    X-Custom-Header: "${CUSTOM_VALUE:-default_value}"
```

**Python Environment Variables:**
```python
# Use os.environ with fallbacks
github_token = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
if github_token:
    tools.append(McpToolRef(
        name="github",
        server=HttpTransport(
            url="https://api.githubcopilot.com/mcp/",
            headers={"Authorization": f"Bearer {github_token}"}
        )
    ))
```

### 3. Error Handling and Resilience

**Timeout Configuration:**
```yaml
# Set appropriate timeouts for different services
- mcp:
    name: fast_service
    server:
      type: http
      url: "https://fast-api.example.com/mcp"
      timeout: 5  # Quick response expected

- mcp:
    name: slow_service
    server:
      type: http
      url: "https://slow-api.example.com/mcp"
      timeout: 30  # Allow for processing time
```

**Fallback Strategies:**
```python
# Provide multiple tool options for similar functionality
async def get_required_tools(self) -> list[AnyTool]:
    tools = [
        # Always include Streetrace tools as fallback
        StreetraceToolRef(module="fs_tool", function="read_file"),
    ]
    
    # Add MCP tools if available
    if can_use_advanced_filesystem():
        tools.append(McpToolRef(name="filesystem", server=...))
    
    return tools
```

### 4. Performance Optimization

**Tool Specificity:**
```yaml
# Specify only needed tools to reduce overhead
- mcp:
    name: github
    server: { ... }
    tools: ["create_issue", "list_repos"]  # Only what you need

# vs.

- mcp:
    name: github
    server: { ... }
    tools: []  # All tools (higher overhead)
```

**Resource Management:**
```python
# Tools are automatically managed by ToolProvider
# No manual cleanup required - lifecycle is handled automatically
```

## Troubleshooting

### Common Issues

**1. Tool Not Found Error**
```
ValueError: Tool 'nonexistent_tool' not found
```
**Solution:** Verify tool names and availability:
```python
# Check available Streetrace tools
from streetrace.tools.definitions import list_tools
available = list_tools(Path.cwd())

# Verify MCP server is accessible
# Check command/URL accessibility manually
```

**2. MCP Connection Timeouts**
```
TimeoutError: MCP server connection timeout
```
**Solution:** Adjust timeout settings and verify connectivity:
```yaml
- mcp:
    name: slow_server
    server:
      type: http
      url: "https://api.example.com/mcp"
      timeout: 30  # Increase timeout
```

**3. Authentication Failures**
```
AuthenticationError: Invalid credentials
```
**Solution:** Verify environment variables and token validity:
```bash
# Check environment variables
echo $GITHUB_PAT
echo $API_TOKEN

# Test API access manually
curl -H "Authorization: Bearer $GITHUB_PAT" https://api.github.com/user
```

**4. Import Errors with Callable Tools**
```
ImportError: Cannot import 'mymodule.utils:helper_function'
```
**Solution:** Verify import path and function signature:
```python
# Test import manually
from mymodule.utils import helper_function

# Ensure function is callable and properly exported
```

### Debugging Tools

**Enable Debug Logging:**
```python
import logging
logging.getLogger("streetrace.tools").setLevel(logging.DEBUG)
```

**Tool Provider Inspection:**
```python
# In your agent's create_agent method
logger.info(f"Received tools: {[type(tool).__name__ for tool in tools]}")
```

**YAML Validation:**
```bash
# Use the built-in validator
streetrace --validate-agent path/to/agent.yml
```

## Advanced Patterns

### 1. Conditional Tool Loading

**Environment-Based:**
```python
async def get_required_tools(self) -> list[AnyTool]:
    tools = [
        # Core tools always included
        StreetraceToolRef(module="fs_tool", function="read_file"),
    ]
    
    # Production-only tools
    if os.environ.get("ENVIRONMENT") == "production":
        tools.append(McpToolRef(name="monitoring", server=...))
    
    # Development-only tools
    if os.environ.get("ENVIRONMENT") == "development":
        tools.append(McpToolRef(name="debug_server", server=...))
    
    return tools
```

**Feature-Flag Based:**
```yaml
# Use environment variables as feature flags
tools:
  - streetrace:
      module: fs_tool
      function: read_file
  
  # Conditional MCP tool based on feature flag
  - mcp:
      name: experimental_feature
      server:
        type: http
        url: "${EXPERIMENTAL_API_URL}"
        headers:
          Authorization: "Bearer ${EXPERIMENTAL_TOKEN}"
    # This tool is only added if environment variables are set
```

### 2. Tool Composition Patterns

**Layered Approach:**
```yaml
# Base functionality
- streetrace:
    module: fs_tool
    function: read_file

# Enhanced functionality
- mcp:
    name: filesystem
    server:
      type: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem"]
    tools: ["edit_file"]  # Complementary to read_file

# Specialized functionality
- mcp:
    name: git
    server:
      type: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-git"]
    tools: ["commit", "push"]
```

**Domain-Specific Tool Groups:**
```python
def get_web_dev_tools() -> list[AnyTool]:
    return [
        StreetraceToolRef(module="fs_tool", function="read_file"),
        StreetraceToolRef(module="fs_tool", function="write_file"),
        McpToolRef(name="npm", server=...),
        McpToolRef(name="webpack", server=...),
    ]

def get_data_science_tools() -> list[AnyTool]:
    return [
        StreetraceToolRef(module="fs_tool", function="read_file"),
        McpToolRef(name="jupyter", server=...),
        McpToolRef(name="database", server=...),
    ]

async def get_required_tools(self) -> list[AnyTool]:
    domain = os.environ.get("AGENT_DOMAIN", "general")
    
    if domain == "web_dev":
        return get_web_dev_tools()
    elif domain == "data_science":
        return get_data_science_tools()
    else:
        return get_general_tools()
```

### 3. Dynamic Tool Configuration

**Runtime Server Discovery:**
```python
async def get_required_tools(self) -> list[AnyTool]:
    tools = []
    
    # Discover available MCP servers
    available_servers = await discover_mcp_servers()
    
    for server_info in available_servers:
        if server_info.name == "github" and server_info.available:
            tools.append(McpToolRef(
                name="github",
                server=server_info.transport_config
            ))
    
    return tools
```

**Configuration-Driven Tools:**
```yaml
# External configuration file: tools.yml
servers:
  - name: github
    enabled: true
    server:
      type: http
      url: "https://api.githubcopilot.com/mcp/"
      headers:
        Authorization: "Bearer ${GITHUB_PAT}"
  
  - name: database
    enabled: false  # Disabled for this agent
    server:
      type: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-sqlite"]
```

### 4. Tool Security Patterns

**Credential Management:**
```python
from streetrace.utils.credentials import get_secure_credential

async def get_required_tools(self) -> list[AnyTool]:
    # Secure credential retrieval
    github_token = get_secure_credential("github_pat")
    
    return [
        McpToolRef(
            name="github",
            server=HttpTransport(
                url="https://api.githubcopilot.com/mcp/",
                headers={"Authorization": f"Bearer {github_token}"}
            )
        )
    ]
```

**Restricted Tool Access:**
```yaml
# Limit tools to specific operations
- mcp:
    name: github
    server: { ... }
    tools: ["list_repos", "get_repo_info"]  # Read-only operations only

- mcp:
    name: filesystem
    server: { ... }
    tools: ["read_file", "get_file_info"]  # No write operations
```

This comprehensive manual provides senior engineers with everything needed to effectively configure and manage tools in Streetrace agents. The examples are based on real implementations from the codebase and follow established patterns for production use.