import os
from google import genai  # https://googleapis.github.io/python-genai/genai.html
from google.genai import types
import tools.fs_tool as fs_tool
import tools.search as search
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='generation.log')

# Configure your API key
api_key = os.environ.get('GEMINI_API_KEY')  # Get the API key from the environment variable
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
client = genai.Client(api_key=api_key)

# https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
class ansi_colors:
    USER = '\x1b[1;32;40m'
    MODEL = '\x1b[1;37;40m'
    MODELERROR = '\x1b[1;37;41m'
    TOOL = '\x1b[1;34;40m'
    TOOLERROR = '\x1b[1;34;41m'
    DEBUG = '\x1b[0;35;40m'
    RESET = '\x1b[0m'

MAX_TOKENS = 2**20
SYSTEM = """
You are an experienced software engineer implementing code for a project working as a peer engineer
with the user. Fullfill all your peer user's requests completely and following best practices and intentions.
If can't understand a task, ask for clarifications.
For every step, remember to adhere to the SYSTEM MESSAGE.
You are working with source code in the current directory (./) that you can access using the provided tools.
For every request, understand what needs to be done, then execute the next appropriate action.

1. Please use provided functions to retrieve the required information.
2. Please use provided functions to apply the necessary changes to the project.
3. When you need to implement code, follow best practices for the given programming language.
4. When applicable, follow software and integration design patterns.
5. When applicable, follow  SOLID principles.
6. Document all the code you implement.
7. If there is no README.md file, create it describing the project.
8. Create other documentation files as necessary, for example to describe setting up the environment.
9. Create unit tests when applicable. If you can see existing unit tests in the codebase, always create unit tests for new code, and maintain the existing tests.
10. Run the unit tests and static analysis checks, such as lint, to make sure the task is completed.
11. After completing the task, please provide a summary of the changes made and update the documentation.

Remember, the code is located in the current directory (./) that you can access using the provided tools.
Remember, if you can't find a specific location in code, try searching through files for close matches.
Remember, always think step by step and execute one step at a time.
Remember, never commit the changes.
"""

# Define the tool configuration
tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.list_directory',
            description='List information about the files and directories in the requested directory.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the directory to retrieve the contents from.'
                    )
                },
                required=['path']  # corrected required parameter name
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.read_file',
            description='Read file contents.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the file to retrieve the contents from.'
                    ),
                    'encoding': types.Schema(
                        type='STRING',
                        description='Text encoding to use. Defaults to \"utf-8\".'
                    )
                },
                required=['path']  # corrected required parameter name
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.write_file',
            description='Write content to a file. Overwrites the file if it already exists.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'path': types.Schema(
                        type='STRING',
                        description='Path to the file to write to.'
                    ),
                    'content': types.Schema(
                        type='STRING',
                        description='New copntent of the file.'
                    ),
                    'encoding': types.Schema(
                        type='STRING',
                        description='Text encoding to use. Defaults to \"utf-8\".'
                    )
                },
                required=['path']  # corrected required parameter name
            )
        )
    ]),

    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='fs_tool.execute_cli_command',
            description='Executes a CLI command and returns the output, error, and return code.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'command': types.Schema(
                        type='STRING',
                        description='The CLI command to execute.'
                    )
                },
                required=['command']
            )
        )
    ]),
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name='search.search_files',
            description='Searches for text occurrences in files given a glob pattern and a search string.',
            parameters=types.Schema(
                type='OBJECT',
                properties={
                    'pattern': types.Schema(
                        type='STRING',
                        description='Glob pattern to match files.'
                    ),
                    'search_string': types.Schema(
                        type='STRING',
                        description='The string to search for.'
                    )
                },
                required=['pattern', 'search_string']
            )
        )
    ]),
]


tools_dict = {
    'fs_tool.list_directory': fs_tool.list_directory,
    'fs_tool.read_file': fs_tool.read_file,
    'fs_tool.write_file': fs_tool.write_file,
    'fs_tool.execute_cli_command': fs_tool.execute_cli_command,
    'search.search_files': search.search_files
}


def get_non_empty_fields(obj):
    non_empty_fields = {}
    for attribute, value in obj.__dict__.items():
        if value:  # Checks for truthiness (not None, not empty string/list/dict, not 0, not False)
            non_empty_fields[attribute] = value
    return non_empty_fields



def pretty_print(contents: list[types.Content]) -> str:
    """
    Pretty print the content of the response.
    """
    # result:
    #  - role: part type: {content}, part type: {content}, etc
    #  - role: part type: {content}, part type: {content}, etc
    # etc
    buff = ''
    counter = 0
    for content in contents:
        buff += f'\nContent {counter + 1}:'
        if not content:
            buff += '\nNONE'
        else:
            buff += f'\n - {content.role}: '
            for part in content.parts:
                buff += ", ".join(
                    [attribute + ": " + str(value).strip()
                    for attribute, value in part.__dict__.items()
                    if value is not None])
        counter += 1
    return buff

def generate_with_tool(prompt, conversation_history =None):
    """
    Generates content using the Gemini model with the custom tool,
    maintaining conversation history.
    """
    # Initialize conversation history if it's None
    if conversation_history is None:
        conversation_history = []

    print(ansi_colors.USER + prompt + ansi_colors.RESET)
    logging.info("User prompt: %s", prompt)

    # Add the user's prompt to the conversation history
    user_prompt_content = types.Content(
        role='user',
        parts=[types.Part.from_text(text=prompt)]
    )
    conversation_history.append(user_prompt_content)
    contents = conversation_history.copy()

    cont = True
    request_count = 0
    # Set a maximum token limit
    while cont:
        request_parts = []
        response_parts = []
        response_text = ''
        finish_reason = ''
        finish_message = ''
        try:
            token_count = client.models.count_tokens(
                model='gemini-2.0-flash-001', contents=contents)
            while token_count.total_tokens > MAX_TOKENS:
                logging.debug(
                    f"Exceeding token limit ({token_count} > {MAX_TOKENS}), "
                    "removing the oldest content item.")
                contents.pop(0)
                token_count = client.models.count_tokens(
                    model='gemini-2.0-flash-001', contents=contents)
            request_count += 1
            logging.info(
                f"Starting chunk processing {request_count} with "
                f"{len(contents)} content items and {token_count} tokens.")
            logging.debug("Start generation with contents:\n%s", pretty_print(contents))
            for chunk in client.models.generate_content_stream(
                model='gemini-2.0-flash-001',
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=tools,
                    system_instruction=SYSTEM,
                    automatic_function_calling=
                    types.AutomaticFunctionCallingConfig(disable=True),
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'))
                )
            ):
                logging.debug("Generated chunk:\n%s", chunk)
                try:
                    finish_reason = chunk.candidates[0].finish_reason or 'None'
                    finish_message = chunk.candidates[0].finish_message or 'None'
                    if chunk.text:
                        print(ansi_colors.MODEL + chunk.text + ansi_colors.RESET, end='')
                        response_text += chunk.text
                    if chunk.function_calls:
                        if len(response_text) > 0:
                            request_parts += [types.Part(text=response_text)]
                            response_text = ''
                        for function_call in chunk.function_calls:
                            print(ansi_colors.TOOL + function_call.name + ": " + str(function_call.args) + ansi_colors.RESET)
                            logging.info(f"Function call: {function_call}")
                            request_parts.append(
                                types.Part(function_call=function_call))
                            # Validate the function call against the tool definitions
                            if function_call.name not in tools_dict:
                                function_response = {
                                    'error': f'Missing function: {function_call.name}'
                                }
                                print(ansi_colors.TOOLERROR + f"Missing function: {function_call.name}" + ansi_colors.RESET)
                                logging.error(
                                    f"Missing function: {function_call.name}")
                            else:
                                try:
                                    logging.debug(
                                        f"Calling function {function_call.name} "
                                        f"with arguments: {function_call.args}")  # Added logging here
                                    result = tools_dict[function_call.name](**function_call.args)
                                    function_response = {'result': result}
                                    print(ansi_colors.TOOL + str(result) + ansi_colors.RESET)
                                    logging.info(f"Function result: {result}")
                                except Exception as e:
                                    function_response = {'error': str(e)}
                                    print(ansi_colors.TOOLERROR + str(e) + ansi_colors.RESET)
                                    logging.warning(
                                        f"Function call error in "
                                        f"{function_call.name}: {e}")  # Added function name to the log
                            response_parts.append(
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        id=function_call.id,
                                        name=function_call.name,
                                        response=function_response)))
                except Exception as e:
                    logging.error(f"Error processing chunk: {e}")
                    logging.debug(f"Chunk when error occurred: {chunk}")  # Added logging here
                    print(ansi_colors.MODELERROR +
                          "\nError processing chunk. See logs for details." +
                          ansi_colors.RESET)
        except Exception as e:
            logging.error(f"Error during content generation: {e}")
            logging.error(f"Last contents: {pretty_print(contents)}")
            logging.debug(f"Last raw contents: {contents}")
            print(ansi_colors.MODELERROR +
                  "\nError during content generation. See logs for details." +
                  ansi_colors.RESET)
            break  # Stop the loop if there's an error during content generation

        if len(response_text) > 0:
            request_parts += [types.Part(text=response_text)]
            response_text = ''
        model_response_content = types.Content(
            role='model',
            parts=request_parts)
        tool_response_content = None
        if len(response_parts) > 0:
            tool_response_content = types.Content(
                role='tool',
                parts=response_parts)

        contents.append(model_response_content)
        conversation_history.append(model_response_content)
        
        if tool_response_content:
            contents.append(tool_response_content)
            conversation_history.append(tool_response_content)

        cont = len(response_parts) > 0
    print(ansi_colors.MODEL + finish_reason + ": " + finish_message +
          ansi_colors.RESET)
    logging.info(
        f"Model has finished with reason {finish_reason}: {finish_message}")
    return conversation_history
