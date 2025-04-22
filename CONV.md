In llm/claude.py I have several blocks that handle data conversions. There are three data formants - the common format managed by llm/wrapper.py, provider response format (e.g. messages returned from Claude's streaming client.messages.create function), and provider input format (e.g., messages accepted by client.messages.create function. The data flow is - we accumulate messages in the Common format, then convert them to provider input format to send a request to the provider, and then convert the messages from provider's response to the Common format to put them back into history. Currently this happens in several places. ContentBlockChunkWrapper helps access data in response messages to process them, then Claude.update_history helps convert them to the Common format, and Claude.transform_history converts the Common format history messages into provider-specific format. Also, Claude.append_to_history allows adding processed messages to provider history.

The overall logic is to continuously maintain the communication history in the Common format, transform it to provider-specific format when sending a request to the provider, then receive new messages from the provider, allow other parts of the application to process those messages, then loop with the provider and the tools until the process is done, and finally store the new final conversation history in the Common format. The loop between the provider and tools happens using the ContentBlockChunkWrapper and Claude.update_history functions.

There are other providers like Claude, including Gemini, ChatGPT, and ollama, which is why the history needs to be maintained in the Common format.

The problem is that currently the data transformation code is spread across the Claude.py, and difficult to test. Please find a solution to implement a SOLID data adapter that will encapsulate all data transformation logic for the given provider, that is easy to test and maintain. Create data adapters for Gemini, ChatGPT, and ollama.

Before starting to code, please analyze the current implementation, evaluate alternative approaches to implementation, and keep asking clarification questions about the implementation until until I say stop, and only then start coding.

===

Extract an abstract base class from llm/claude_converter.py called TypeConverter with generic parameters for types owned by Claude sdk (e.g., anthropic.types.MessageParam)

===

Investigate claude, gemini, and openai implementations of LLMAPI and HistoryConverter in llm folder, and refactor the current ollama implementaion to match the code structure

===

Let's implement @mentions in user prompts. When the user uses '@' to mention something, we will try to see if the user is mentioning an existing file using its relative path. The files have to always be in the current working directory. When the mention is detected, let's add the mentioned files contents as additional context items in the additional history messages before the user's prompt.

For example, if user's prompt is:

Describe this project based on @README.md

Then we will add the following items into the conversation history:

- user message 1:
Contents of ./README.md:

```md
...CONTENTS OF THE FILE...
```

- user message 2:
Describe this project based on @README.md

Summarize the requirements and describe the alternative approaches. Keep asking questions to clarify requirements before starting to implement.

===

It seems tests/test_mentions.py fails the test_multiple_valid_mentions test due to the trailing dot in the prompt. What is the best way to fix it?

===

There are multiple things happening before the prompt is sent to the model. These include adding the system message, context files, parsing mentions. See @main.py.
Potentially, there will be even more things, like re-writing and enhancing the prompt and handling intermediate instructions.
There are also special prompts, such as "exit" and there will be more like that.
Let's think about refactoring this to ensure SOLID principles, testability, and extensibility.
What are the potential solutions?
Describe the alternative approaches. Keep asking questions to clarify requirements before starting to implement.

===

In @app/application.py there is conversation history object for both interactive and non-interactive mode. Let's implement conversation history management over app restarts. The conversations have to store the entire history, and every turn has to indicate the backend and model used for this turn. Each conversation history will have an ID generaged as YYYYMMDD_HHmmSSUTC, and the file name for the conversation has to match its id. The history needs to be stored in .history folder within the current directory. We should save the frequency when the user enters a new message, and when the processing of assistant's message is complete. Implement another optional command line argument to specify the conversation history (applicable to both interactive and non-interactive modes). If the argument is specified, the history needs to be hydrated from the referenced history. If an invalid history ID is provided by the user, we should immediately error out and exit. Let's store the history as markdown files that look nice when rendered, but include special macros that we can use when parsing and saving to allow parsing as a proper history. The big advantage of storing in mardown is that user can immediately render the result, use a markdown editor to edit it, etc., so lets make sure the rendered format shows proper formatting for turns, roles, and all messages. Describe the alternative approaches. Keep asking questions to clarify requirements before starting to implement.

===

This is a python project with a lot of python code. I want to make sure the code is perfect from the lint, style, and documentation perspectives. Could you look around the files and folders and suggest a good project structure and a CI pipeline that guarantees high code quality and reports or auto-fixes all potential code style issues?

===

Let's implement token counting for gemini. Whenever the response is received, we need to get token counts from response usage_metadata. What we need is to know how much tokens this conversation history consumes (prompt_token_count), how much of it is cached (cached_content_token_count), and candidates_token_count. We can use these token counds in the manage_conversation_history to try and fit the conversation history into the context window. We also need to accumulate tokens and print stats for every response: numbers for the current response, and total numbers for this working session.


===

Let's make sure we have 100% test coverage for @src/streetrace/llm/claude/impl.py. The existing tests might be heavily outdated, please go ahead and remove or re-write implausible tests, the ground truth is in the implementation. Please keep the implementation as-is, unless there are obvious issues with it. I want the code to be concise and assertive, may be , so you might as well re-write it and remove parts that do not make senseare not present in the actual converter.py.
Make sure you activate venv when running tests, so that you have claude and may be /impl right dependencies.
Make sure to check with the @CONTRIBUTING.do not make sensemd when introducing changes.


===

run pytest and try to fix failing tests. Do not modify files under src/streetrace as they work as expected.

Claude:
- Ignored the "do not modify" part and started making pointless changes in the codebase
- Very slow in general, but even then, rate limits made imposible to dig through everything.

Gemini:
- Ignored the "do not modify" but the modifications were at least not that dumb
- Errored out with 500, but fixed over a half of the tests driving coverage to 60%

===

check git diff, also check individual file changes, and suggest a concise and clear atomic commit message for this change

===

TEST prompt

All files in the ./tmp/inputs directory contain numbers. Sum up thouse numbers and write a new file named as YYYYMMDD_HHMMSS.txt in the ./tmp/outputs directory with the resulting value.

===

The commands, like 'history', 'exit', and 'quit' should start with a slash, allowing the user to type a slash and then the command name. When typing slash, the autocomplete should trigger suggesting available commands. To allow that, @src/streetrace/path_completer.py should be refactored leveraging composition pattern. The main Completer called PromptCompleter will handle all completions, leveraging helper classes to provide those completions. PromptCompleter will be initialized with a list of helper completer classes. When completions are requested, it will iterate through all available helper completers and provide a concatenated list of all completioons.


===

The raw chunks in the ChunkWrapper defined in @src/streetrace/llm/history_converter.py can contain usage information.
Please create a new class in @src/streetrace/llm/wrapper.py that contains two fields: input_tokens and output_tokens, and a function in ChunkWrapper to allow getting this information from the chunk if it's present.
In self.provider.generate in @src/streetrace/ui/interaction_manager.py, if a chunk contains usage information, show it in the "Working" progress indicator in the form of: "Working, io tokens: {n_input}/{n_output}, total requests: n_requests." showing the cumulative token stats and the total number of tokens reported during this run of process_prompt. You can use status.update(new_status_message) to update the status message.
The numbers should be updated every time the usage information is received from the ChunkWrapper or a self.provider.generate finishes.
The status has to stay just "Working, total requests: n_requests" until the first usage information is received.