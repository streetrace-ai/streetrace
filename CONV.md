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

===

---

### 🧠 **Instruction: Chat History Markdown Format with YAML Metadata**

> **Goal**: Serialize and deserialize chat history in a single, human-readable Markdown file with metadata per message.

---

#### ✅ **Format Specification**
Each chat message must be written in the following structure:

```markdown
---
role: <user|assistant|system|tool>
timestamp: <ISO 8601 string>
model: <model name or null>
---

<Multiline message content in Markdown>
```

- Metadata is written as a YAML front matter block (`---`).
- Message text follows the metadata block and may contain rich Markdown formatting (e.g. bold, italics, lists, code blocks).
- One message follows another without additional wrappers.

---

#### 📤 **Serialization (Python)**

```python
import yaml

def serialize_chat_to_markdown(messages, path):
    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            metadata = {
                'role': msg['role'],
                'timestamp': msg['timestamp'],
                'model': msg.get('model'),
            }
            f.write(f"---\n{yaml.safe_dump(metadata)}---\n\n{msg['text'].rstrip()}\n\n")
```

---

#### 📥 **Deserialization (Python)**

```python
import yaml, re

def deserialize_chat_from_markdown(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = re.split(r'^---$', content, flags=re.MULTILINE)
    messages = []

    for i in range(1, len(parts) - 1, 2):
        metadata = yaml.safe_load(parts[i])
        text = parts[i + 1].strip()
        messages.append({**metadata, 'text': text})

    return messages
```

---

#### ✅ **Rendering Goals**
- File should render cleanly in Markdown viewers.
- Easy for humans to browse, edit, and version-control (e.g. Git).
- Metadata must remain visible and editable.

---











In @app/application.py there is conversation history object for both interactive and non-interactive mode. We need to implement conversation history management over app restarts. This includes:

1. Whenever the history is updated (a user sends a message, or LLM responds) the updated history needs to be saved on disk in the common format.
2. The history will be saved in Markdown format defined below. It should look clean when rendered as Markdown, and allow reliable and error-prone serialization and deserialization.
3. Every stored conversation turn has to contain all available turn information: role, text, tool calls, and tool results.
4. Conversation history will have an ID generaged as YYYYMMDD_HHmmSSUTC, and the file name for the conversation has to match its id.
5. The history needs to be stored in .history folder within the current directory.
6. Implement an optional command line argument to specify the conversation history ID (applicable to both interactive and non-interactive modes). If the argument is specified, the history needs to be hydrated from the referenced history file. If an invalid history ID is provided by the user, we should immediately error out and exit.

Let's store the history as markdown files that look nice when rendered, but include special macros that we can use when parsing and saving to allow parsing as a proper history. The big advantage of storing in mardown is that user can immediately render the result, use a markdown editor to edit it, etc., so lets make sure the rendered format shows proper formatting for turns, roles, and all messages. Describe the alternative approaches. Keep asking questions to clarify requirements before starting to implement.


---

Take a look at @src/streetrace/ui/interaction_manager.py. This class is responsible for driving the main conversation loop. The process_prompt method seems to have a high cyclomatic complexity and a lot of flow control conditions. Can you suggest ideas for how to simplify it?

---

Take a look at @src/streetrace/ui/interaction_manager.py. Let's create a set of unit tests that test for `process_prompt` to establish ground rules for this function. Please use a mocked `self.provider`. Treat `InteractionManager` as a black box, so we can re-use these tests during refactoring. The current implementation may or may not fail these tests because it does not necessarily meet the ground truth criteria.

The ground rules I'm thinking of are:

* when the `process_prompt` finishes, it returns a FinishStatus message containing reason_to_finich, and token and request stats.

* when initial or any consequent call to `self.provider.generate` throws a `RetriableError`, we expect `retry_err.max_retries` number of retries, after which the loop exits with the right reason.
* when initial or any consequent call to `self.provider.generate` throws a `RetriableError`, we expect the requested wait period is waited. You can introduce another parameter in `InteractionManager` to inject a waiter.
* when `self.provider.generate` results in tool calls, we expect the thinking session will continue.
* when `self.provider.generate` does not provide a finish_reason, we expect the thinking session will continue.
* when `self.provider.generate` does not throw and does not yield either tool calls or a reason to finish, the thinking session will continue for _DEFAULT_MAX_RETRIES attemts. In this scenario, if provider returns any assistant messages, they will all be stored in history.
* when initial or any consequent call to `self.provider.generate` or `self.tools.call_tool` throws any error, we expect that the provider and common history contain all previous turn messages, but not the failed conversation turn.
* when initial or any consequent call to `self.provider.generate` or `self.tools.call_tool` throws any non-retriable error, we expect the thinking session stops and the reason_to_finish contains a valid reason.
* when `RetriableError` does not specify `max_retries`, the default is used.

Okay, here's a summary of our conversation:

Goal:

The primary goal was to create a robust set of unit tests for the InteractionManager.process_prompt method. The purpose was to define clear behavioral
"ground rules" for this critical function, covering its interaction loop, handling of different AI responses (text, tool calls, finish reasons), error
conditions (retriable errors, non-retriable errors, keyboard interrupts), and history management. These tests would serve as a safety net for future
refactoring and ensure the function behaves as expected.

Outcomes:

 1 Ground Rules Defined: We identified and listed key scenarios and expected behaviors for process_prompt, including normal execution, multi-turn tool
   calls, retries on specific errors, handling of unexpected errors, and behavior during user interruptions.
 2 Test Suite Implemented: I created the test file tests/ui/test_interaction_manager.py and implemented unit tests using pytest and unittest.mock to cover
   the defined ground rules and additional edge cases. The tests were designed to treat InteractionManager as a black box.
 3 Initial Issues Identified: Upon review and simulated execution, we found:
    • Two tests related to retries (test_process_prompt_retriable_error_max_retries and test_process_prompt_no_finish_reason_or_tool_calls_retries) had
      issues (one with test setup, one potentially hanging due to a logic bug in the code under test).
    • Two tests (test_process_prompt_keyboard_interrupt and test_process_prompt_non_retriable_error_during_tool_call) were failing, specifically around how
      history was being updated (or not updated) when exceptions occurred mid-turn.
 4 Code and Test Fixes:
    • I corrected the test setup for test_process_prompt_retriable_error_max_retries.
    • I identified and fixed a potential infinite loop in InteractionManager.process_prompt related to retrying empty turns.
    • I adjusted the logic within InteractionManager.process_prompt's exception handling (KeyboardInterrupt and general Exception) to ensure that incomplete
      turns (e.g., a MODEL message with a tool call request, but no corresponding TOOL result message due to the error) are not added to the main history
      object, aligning the code with the ground rules for error scenarios.
 5 Verification: After applying the fixes, the unit tests are expected to pass, confirming that the InteractionManager.process_prompt implementation now
   aligns with the established ground rules.

In short, we defined the contract for process_prompt, built tests to verify it, used the tests to identify and fix bugs in the implementation, and arrived
at a state where the code meets the specified behavioral requirements.

---

I like the state machine approach. Could you implement that so we can see how it can look? Also, we might want to create classes for Turn data (like the TurnBuffer you mentioned, let's call it Turn), and LoopState that will hold all state information.

LoopState can expose functions to update state in different cases (like Handle Retriable Error, Handle Keyboard Interrupt, etc.)

Handling each type of chunk is easy to read and understand, so we can keep them in one place, perhaps a separate function in the Turn class.

Please implement these changes so we can see how it works.