# StreetRace🚗💨

StreetRace🚗💨 is your agentic AI peer that enables engineers to leverage AI from the command line to automate their workflows.

# How is StreetRace🚗💨 different?

* From Cursor: StreetRace🚗💨 is a CLI that allows full customization of the workflow. It can be a coder, an SRE, or your workflow orchestrator.
* From Replit and Lovable: StreetRace🚗💨 is a universal and fully customizable agent. It's not limited to hosting platforms and uses only the knowledge you provide and workflows you configure.
* From n8n: StreetRace🚗💨 is an agent, not a workflow suite.
* From ChatGPT: StreetRace🚗💨 can use any of 200+ models, or a combination of, and it can run in a container.
* From Claude Code, OpenAI Codex, Amazon Q, etc: StreetRace🚗💨 is designed to let you build a suite of your agents integrated with any other agents via a2a and MCP.

**Project Description:**

StreetRace🚗💨 defines a set of tools that the AI model can use to interact with the file system (listing directories, reading/writing files, and executing CLI commands) and search for text within files. The core logic uses a common LLMAPI interface implemented by provider-specific classes (Anthropic, Gemini, OpenAI, Ollama) to handle interactions with different AI models. This architecture makes it easy to switch between providers while maintaining consistent functionality.

**Key Components:**

* `ai_interface.py`: Defines the abstract base LLMAPI class that all provider implementations must follow.
* `claude_provider.py`: Implements the LLMAPI interface for Anthropic's Anthropic models.
* `gemini_provider.py`: Implements the LLMAPI interface for Google's Gemini models.
* `openai_provider.py`: Implements the LLMAPI interface for OpenAI models.
* `ollama_provider.py`: Implements the LLMAPI interface for locally hosted models via Ollama.
* `ai_provider_factory.py`: Factory functions to create and use the appropriate provider.
* `main.py`: Provides a command-line interface for interacting with the AI providers.
* `tools/fs_tool.py`: Implements file system tools (list directory, read file, write file, execute CLI command).
* `tools/search.py`: Implements a tool for searching text within files.
* `completer.py`: Implements path (`@`) and command (`/`) autocompletion for the interactive prompt.

**Workflow:**

1. The user provides a prompt through the command-line interface in `main.py`.
2. The appropriate AI provider is selected based on command line arguments or available API keys.
3. The prompt is passed to the provider's `generate_with_tool` method.
4. The provider sends the prompt and conversation history to the AI model.
5. The AI model processes the input and may call one of the defined tools.
6. If a tool is called, the provider executes the corresponding function in `tools/fs_tool.py` or `tools/search.py`.
7. The result of the tool execution is sent back to the AI model.
8. The AI model generates a response, which is displayed to the user.
9. The conversation history is updated, and the process repeats.

## Tools

These are functions the AI model can request to execute:

* `fs_tool.list_directory`: Lists files and directories in a given path.
* `fs_tool.read_file`: Reads the content of a file.
* `fs_tool.write_file`: Writes content to a file.
* `fs_tool.execute_cli_command`: Executes a CLI command with full interactive capabilities.
* `fs_tool.find_in_files`: Searches for text in files matching a glob pattern.

## Usage

Run the application using `python src/streetrace/main.py` (or `python -m streetrace.main` if installed).

### Command Line Arguments

StreetRace🚗💨 supports the following command line arguments:

```
python src/streetrace/main.py [--provider {anthropic|gemini|ollama|openai}] [--model MODEL_NAME] [--prompt PROMPT] [--path PATH]
```

Options:
- `--provider` - Choose AI provider (anthropic, gemini, ollama, or openai)
- `--model` - Specific model name to use (e.g., anthropic-3-opus-20240229, gemini-1.5-flash, llama3:8b, or gpt-4o)
- `--prompt` - Prompt to send to the AI model (skips interactive mode if provided)
- `--path` - Specify which path to use as the working directory for all file operations
- `--debug` - Enable debug logging.

If no provider is specified, StreetRace🚗💨 will automatically select an AI model based on the available API keys in the following order:
1. Anthropic (if ANTHROPIC_API_KEY is set)
2. Gemini (if GEMINI_API_KEY is set)
3. OpenAI (if OPENAI_API_KEY is set)
4. Ollama (if OLLAMA_API_URL is set or Ollama is installed locally)

#### Working with Files in Another Directory

The `--path` argument allows you to specify a different working directory for all file operations:

```
python src/streetrace/main.py --path /path/to/your/project
```

This path will be used as the working directory (work_dir) for all tools that interact with the file system, including:
- list_directory
- read_file
- write_file
- find_in_files

This feature makes it easier to work with files in another location without changing your current directory.

### Interactive Mode

When run without `--prompt`, StreetRace🚗💨 enters interactive mode.

#### Autocompletion

- Type `@` followed by characters to autocomplete file or directory paths relative to the working directory.
- Type `/` at the beginning of the line to autocomplete available internal commands.

#### Internal Commands

These commands can be typed directly into the prompt (with autocompletion support):

* `/exit`: Exit the interactive session.
* `/quit`: Quit the interactive session.
* `/history`: Display the conversation history.
* `/compact`: Summarize conversation history to reduce token count.
* (Future commands like `/help`, `/config` could be added here)

For detailed information about the `/compact` command, see [docs/commands/compact.md](docs/commands/compact.md).

### Non-interactive Mode

You can use the `--prompt` argument to run StreetRace🚗💨 in non-interactive mode:

```
python src/streetrace/main.py --prompt "List all Python files in the current directory"
```

This will execute the prompt once and exit, which is useful for scripting or one-off commands.

### Interactive CLI Execution

The `execute_cli_command` tool supports fully interactive subprocesses:

- Standard input/output/error of the subprocess are connected to the application's standard input/output/error
- Users can see real-time output from the subprocess
- Users can provide input when the subprocess prompts for it
- All output is still captured and returned in the result for the AI model to analyze

This allows for interactive use of command-line tools, such as text editors, REPLs, or any program that expects user input. For example, the AI can run a Python interpreter and let you interactively test code:

```
> Please run a Python interpreter so I can test some code
Running Python interpreter...
Type Python code at the prompt:

Python 3.8.10 (default, Nov 14 2022, 12:59:47)
[GCC 9.4.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> print("Hello, interactive world!")
Hello, interactive world!
>>>
```

To exit interactive processes, use the standard method for that program (such as Ctrl-D for Python REPL or `:q` for vim).

### System Message Customization

StreetRace🚗💨 centralizes system message handling in `main.py` and passes it to the provider implementations. By default, it looks for a system message in `.streetrace/system.md` and uses a default message if not found.

You can also programmatically specify a custom system message when using the `generate_with_tool` function:

```python
from ai_provider_factory import generate_with_tool

# Define a custom system message
system_message = """You are a helpful AI assistant specializing in Python development.
You provide clear, concise explanations and write clean, well-documented code."""

# Use the custom system message
conversation_history = generate_with_tool(
    "Create a simple hello world script",
    tools=tools,
    call_tool=call_tool_function,
    provider_name="anthropic",  # optional - will auto-detect if not specified
    system_message=system_message
)
```

### AI Provider Architecture

StreetRace🚗💨 uses a common interface for all AI providers:

1. **AIProvider Interface**: The `AIProvider` abstract base class in `ai_interface.py` defines methods that all providers must implement:
   - `initialize_client()` - Set up the provider client
   - `transform_tools()` - Convert tool definitions to provider-specific format
   - `pretty_print()` - Format messages for logging
   - `manage_conversation_history()` - Handle token limits
   - `generate_with_tool()` - Core method for generating content with tools

2. **Provider Implementations**:
   - `AnthropicProvider` - Anthropic's Anthropic implementation
   - `GeminiProvider` - Google's Gemini implementation
   - `OpenAIProvider` - OpenAI implementation
   - `OllamaProvider` - Ollama implementation for local models

3. **Factory Pattern**: The `ai_provider_factory.py` module provides functions to create and use the appropriate provider:
   - `get_ai_provider()` - Returns the appropriate provider based on arguments or available API keys
   - `generate_with_tool()` - Convenience function for using the provider

This architecture makes it easy to add new AI providers or switch between them while maintaining consistent functionality.

## Environment Setup

To use these tools, you need to set one of the following environment variables:
- `ANTHROPIC_API_KEY` for Anthropic AI model
- `GEMINI_API_KEY` for Gemini AI model
- `OPENAI_API_KEY` for OpenAI model
- `OLLAMA_API_URL` (optional) for local Ollama models

### Using with OpenAI

StreetRace🚗💨 supports integration with OpenAI's models, such as GPT-4 and GPT-3.5 Turbo.

#### Setup for OpenAI

1. Create an API key at the [OpenAI Platform](https://platform.openai.com/api-keys).
2. Set the API key in your environment:
   ```
   export OPENAI_API_KEY=your_openai_api_key_here
   ```
3. (Optional) If you're using a custom API endpoint, set it as an environment variable:
   ```
   export OPENAI_API_BASE=your_custom_api_endpoint
   ```

#### Configuration Options

- **Default Model**: By default, StreetRace🚗💨 uses the `gpt-4-turbo-2024-04-09` model. You can specify a different model using the `--model` argument.
  ```
  python src/streetrace/main.py --provider openai --model gpt-4o-2024-05-13
  ```

#### Usage Examples

Using OpenAI with the default model:
```
python src/streetrace/main.py --provider openai
```

Explicitly selecting OpenAI with a specific model:
```
python src/streetrace/main.py --provider openai --model gpt-3.5-turbo
```

For more details, see [README-openai.md](README-openai.md).

### Using with Ollama

StreetRace🚗💨 supports integration with [Ollama](https://ollama.ai/), allowing you to use locally hosted open-source models.

#### Setup for Ollama

1. Install Ollama on your system. Visit [ollama.ai](https://ollama.ai/) for installation instructions.
2. Pull the model you want to use, for example:
   ```
   ollama pull llama3:8b
   ```
3. Ensure Ollama is running on your system:
   ```
   ollama serve
   ```

#### Configuration Options

- **OLLAMA_API_URL**: (Optional) Set this environment variable to specify a custom URL for the Ollama API. By default, StreetRace🚗💨 will use `http://localhost:11434`.
  ```
  export OLLAMA_API_URL="http://my-ollama-server:11434"
  ```

- **Default Model**: By default, StreetRace🚗💨 uses the `llama3:8b` model. You can specify a different model using the `--model` argument.
  ```
  python src/streetrace/main.py --provider ollama --model mistral:7b
  ```

#### Usage Examples

Using default Ollama model (automatic detection if Ollama is installed):
```
python src/streetrace/main.py --provider ollama
```

Explicitly selecting Ollama with a specific model:
```
python src/streetrace/main.py --provider ollama --model codellama:13b
```

Setting a different Ollama API URL and running with a specific prompt:
```
export OLLAMA_API_URL="http://192.168.1.100:11434"
python src/streetrace/main.py --provider ollama --model llama3:70b --prompt "Create a simple HTTP server in Python"
```

For more details, see [README-ollama.md](README-ollama.md).

## Running tests

To run the tests, execute `python -m unittest tests/*test*.py` or `python -m unittest discover tests`.

To test the interactive CLI functionality, run `python tools/test_cli.py`.