import os
import logging
import anthropic  # pip install anthropic
import json
import time
import tools.fs_tool as fs_tool

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='claude_generation.log')

# Configure your API key
api_key = os.environ.get(
    'ANTHROPIC_API_KEY')  # Get the API key from the environment variable
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
client = anthropic.Anthropic(api_key=api_key)


# ANSI colors for terminal output
class ansi_colors:
    USER = '\x1b[1;32;40m'
    MODEL = '\x1b[1;37;40m'
    MODELERROR = '\x1b[1;37;41m'
    TOOL = '\x1b[1;34;40m'
    TOOLERROR = '\x1b[1;34;41m'
    DEBUG = '\x1b[0;35;40m'
    RESET = '\x1b[0m'
    WARNING = '\x1b[1;33;40m'


MAX_TOKENS = 200000  # Claude 3 Sonnet has a context window of approximately 200K tokens

system_message_path = '.streetrace/system_message.txt'
if os.path.exists(system_message_path):
    try:
        with open(system_message_path, 'r', encoding='utf-8') as f:
            SYSTEM = f.read()
    except Exception as e:
        print(f"Error reading system message file: {e}")
        SYSTEM = "You are an experienced software engineer implementing code for a project working as a peer engineer\nwith the user. Fullfill all your peer user's requests completely and following best practices and intentions.\nIf can't understand a task, ask for clarifications.\nFor every step, remember to adhere to the SYSTEM MESSAGE.\nYou are working with source code in the current directory (./) that you can access using the provided tools.\nFor every request, understand what needs to be done, then execute the next appropriate action.\n\n1. Please use provided functions to retrieve the required information.\n2. Please use provided functions to apply the necessary changes to the project.\n3. When you need to implement code, follow best practices for the given programming language.\n4. When applicable, follow software and integration design patterns.\n5. When applicable, follow SOLID principles.\n6. Document all the code you implement.\n7. If there is no README.md file, create it describing the project.\n8. Create other documentation files as necessary, for example to describe setting up the environment.\n9. Create unit tests when applicable. If you can see existing unit tests in the codebase, always create unit tests for new code, and maintain the existing tests.\n10. Run the unit tests and static analysis checks, such as lint, to make sure the task is completed.\n11. After completing the task, please provide a summary of the changes made and update the documentation.\n\nRemember, the code is located in the current directory (./) that you can access using the provided tools.\nRemember, if you can't find a specific location in code, try searching through files for close matches.\nRemember, always think step by step and execute one step at a time.\nRemember, never commit the changes."
else:
    SYSTEM = "You are an experienced software engineer implementing code for a project working as a peer engineer\nwith the user. Fullfill all your peer user's requests completely and following best practices and intentions.\nIf can't understand a task, ask for clarifications.\nFor every step, remember to adhere to the SYSTEM MESSAGE.\nYou are working with source code in the current directory (./) that you can access using the provided tools.\nFor every request, understand what needs to be done, then execute the next appropriate action.\n\n1. Please use provided functions to retrieve the required information.\n2. Please use provided functions to apply the necessary changes to the project.\n3. When you need to implement code, follow best practices for the given programming language.\n4. When applicable, follow software and integration design patterns.\n5. When applicable, follow SOLID principles.\n6. Document all the code you implement.\n7. If there is no README.md file, create it describing the project.\n8. Create other documentation files as necessary, for example to describe setting up the environment.\n9. Create unit tests when applicable. If you can see existing unit tests in the codebase, always create unit tests for new code, and maintain the existing tests.\n10. Run the unit tests and static analysis checks, such as lint, to make sure the task is completed.\n11. After completing the task, please provide a summary of the changes made and update the documentation.\n\nRemember, the code is located in the current directory (./) that you can access using the provided tools.\nRemember, if you can't find a specific location in code, try searching through files for close matches.\nRemember, always think step by step and execute one step at a time.\nRemember, never commit the changes."

# Define the tools
tools = [{
    "type": "custom",
    "name": "search_files",
    "description":
    "Searches for text occurrences in files given a glob pattern and a search string.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files."
            },
            "search_string": {
                "type": "string",
                "description": "The string to search for."
            }
        },
        "required": ["pattern", "search_string"]
    }
}, {
    "type": "custom",
    "name": "execute_cli_command",
    "description":
    "Executes a CLI command and returns the output, error, and return code.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The CLI command to execute."
            }
        },
        "required": ["command"]
    }
}, {
    "type": "custom",
    "name": "write_file",
    "description":
    "Write content to a file. Overwrites the file if it already exists.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write to."
            },
            "content": {
                "type": "string",
                "description": "New content of the file."
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding to use. Defaults to \"utf-8\"."
            }
        },
        "required": ["path", "content"]
    }
}, {
    "type": "custom",
    "name": "read_file",
    "description": "Read file contents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description":
                "Path to the file to retrieve the contents from."
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding to use. Defaults to \"utf-8\"."
            }
        },
        "required": ["path"]
    }
}, {
    "type": "custom",
    "name": "list_directory",
    "description":
    "List information about the files and directories in the requested directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type":
                "string",
                "description":
                "Path to the directory to retrieve the contents from."
            }
        },
        "required": ["path"]
    }
}]

# Mapping tool names to functions
tools_dict = {
    'list_directory': fs_tool.list_directory,
    'read_file': fs_tool.read_file,
    'write_file': fs_tool.write_file,
    'execute_cli_command': fs_tool.execute_cli_command,
    'search_files': fs_tool.search_files
}


def generate_with_tool(prompt, conversation_history=None, model_name="claude-3-7-sonnet-20250219"):
    """
    Generates content using the Claude model with tools,
    maintaining conversation history.
    
    Args:
        prompt (str): The user's input prompt
        conversation_history (list, optional): The history of the conversation. Defaults to None.
        model_name (str, optional): The name of the Claude model to use. Defaults to \"claude-3-7-sonnet-20250219\".
    
    Returns:
        list: The updated conversation history
    """
    # Initialize conversation history if it's None
    if conversation_history is None:
        conversation_history = []

    print(ansi_colors.USER + prompt + ansi_colors.RESET)
    logging.info("User prompt: %s", prompt)

    # Add the user's prompt to the conversation history
    user_message = {
        'role': 'user',
        'content': [{
            'type': 'text',
            'text': prompt
        }]
    }
    conversation_history.append(user_message)
    messages = conversation_history.copy()

    continue_generation = True
    request_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    last_response = None

    while continue_generation:
        retry_count = 0
        while True:  # This loop handles retries for rate limit errors
            try:
                request_count += 1
                logging.info(
                    f"Starting chunk processing {request_count} with {len(messages)} message items."
                )
                logging.debug("Messages for generation:\n%s", messages)

                # Create the message with Claude
                last_response = client.messages.create(
                    model=model_name,
                    max_tokens=20000,
                    system=SYSTEM,
                    messages=messages,
                    tools=tools)

                logging.debug("Full API response: %s", last_response)
                
                if last_response.usage:
                    total_input_tokens += last_response.usage.input_tokens
                    total_output_tokens += last_response.usage.output_tokens
                
                # Break the retry loop if successful
                break
                
            except anthropic.RateLimitError as e:
                retry_count += 1
                wait_time = 30  # Wait for 30 seconds before retrying
                
                error_msg = f"Rate limit error encountered. Retrying in {wait_time} seconds... (Attempt {retry_count})"
                logging.warning(error_msg)
                print(ansi_colors.WARNING + error_msg + ansi_colors.RESET)
                
                time.sleep(wait_time)
                continue
                
            except Exception as e:
                logging.exception(f"Error during API call: {e}")
                print(ansi_colors.MODELERROR +
                      f"\nError during API call: {e}" +
                      ansi_colors.RESET)
                # For non-rate limit errors, don't retry
                raise

        model_messages = []
        tool_results = []

        for content_block in last_response.content:
            model_messages.append(content_block)
            if content_block.type == 'text':
                print(ansi_colors.MODEL + content_block.text +
                    ansi_colors.RESET, end='')
            elif content_block.type == 'tool_use':

                print(ansi_colors.TOOL + content_block.name + ": " +
                      str(content_block.input) + ansi_colors.RESET)
                logging.info(f"Tool call: {content_block}")


                # Execute the tool if it exists
                if content_block.name not in tools_dict:
                    tool_result = {
                        "error": f"Missing function: {content_block.name}"
                    }
                    print(ansi_colors.TOOLERROR +
                          f"Missing function: {content_block.name}" +
                          ansi_colors.RESET)
                    logging.error(f"Missing function: {content_block.name}")
                else:
                    try:
                        result = tools_dict[content_block.name](**content_block.input)
                        tool_result = {"result": result}
                        print(ansi_colors.TOOL + str(result) +
                              ansi_colors.RESET)
                        logging.info(f"Function result: {result}")
                    except Exception as e:
                        tool_result = {"error": str(e)}
                        print(ansi_colors.TOOLERROR + str(e) +
                              ansi_colors.RESET)
                        logging.warning(
                            f"Function call error in {content_block}: {e}")

                # Add tool result to outputs
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': content_block.id,
                    'content': json.dumps(tool_result) 
                })
                
        messages.append({
            'role': last_response.role,
            'content': model_messages})
        messages.append({
            'role': 'user',
            'content': tool_results})

        conversation_history[len(conversation_history):len(messages)] = messages[len(conversation_history):]

        # Continue only if there were tool calls
        continue_generation = last_response.stop_reason == 'tool_use'

    if last_response:
        print(ansi_colors.MODEL + f"Stop reason: {last_response.stop_reason}" +
              ansi_colors.RESET)
        logging.info(f"Model has finished with reason: {last_response.stop_reason}")

    return conversation_history