In llm/anthropic.py I have several blocks that handle data conversions. There are three data formants - the common format managed by llm/wrapper.py, provider response format (e.g. messages returned from Anthropic's streaming client.messages.create function), and provider input format (e.g., messages accepted by client.messages.create function. The data flow is - we accumulate messages in the Common format, then convert them to provider input format to send a request to the provider, and then convert the messages from provider's response to the Common format to put them back into history. Currently this happens in several places. ContentBlockChunkWrapper helps access data in response messages to process them, then Anthropic.update_history helps convert them to the Common format, and Anthropic.transform_history converts the Common format history messages into provider-specific format. Also, Anthropic.append_to_history allows adding processed messages to provider history.

The overall logic is to continuously maintain the communication history in the Common format, transform it to provider-specific format when sending a request to the provider, then receive new messages from the provider, allow other parts of the application to process those messages, then loop with the provider and the tools until the process is done, and finally store the new final conversation history in the Common format. The loop between the provider and tools happens using the ContentBlockChunkWrapper and Anthropic.update_history functions.

There are other providers like Anthropic, including Gemini, ChatGPT, and ollama, which is why the history needs to be maintained in the Common format.

The problem is that currently the data transformation code is spread across the Anthropic.py, and difficult to test. Please find a solution to implement a SOLID data adapter that will encapsulate all data transformation logic for the given provider, that is easy to test and maintain. Create data adapters for Gemini, ChatGPT, and ollama.

Before starting to code, please analyze the current implementation, evaluate alternative approaches to implementation, and keep asking clarification questions about the implementation until until I say stop, and only then start coding.

===

Extract an abstract base class from llm/claude_converter.py called TypeConverter with generic parameters for types owned by Anthropic sdk (e.g., anthropic.types.MessageParam)

===

Investigate anthropic, gemini, and openai implementations of LLMAPI and HistoryConverter in llm folder, and refactor the current ollama implementaion to match the code structure

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

Let's make sure we have 100% test coverage for @src/streetrace/llm/anthropic/impl.py. The existing tests might be heavily outdated, please go ahead and remove or re-write implausible tests, the ground truth is in the implementation. Please keep the implementation as-is, unless there are obvious issues with it. I want the code to be concise and assertive, may be , so you might as well re-write it and remove parts that do not make senseare not present in the actual converter.py.
Make sure you activate venv when running tests, so that you have anthropic and may be /impl right dependencies.
Make sure to check with the @CONTRIBUTING.do not make sensemd when introducing changes.


===

run pytest and try to fix failing tests. Do not modify files under src/streetrace as they work as expected.

Anthropic:
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

# Create unit tests

Bad thing about this prompt - not focused, no technical details, so the tests are ugly and clunky.

```
Take a look at @src/streetrace/ui/interaction_manager.py. `process_prompt` has a very high cyclomatic complexity. Could you create a minimal unit test to test a set of ground rules `process_prompt` has to follow? Please mock `self.provider`. Treat `InteractionManager` as a black box, so we can re-use these tests during refactoring. The current implementation may or may not fail these tests because it does not necessarily meet the ground truth criteria. Be careful about test timeouts because errors with retries can cause infinite loops.

The ground rules I'm thinking of are:

* when the `process_prompt` finishes, it returns a FinishStatus message containing reason_to_finish, and token and request stats.

* when initial or any consequent call to `self.provider.generate` throws a `RetriableError`, we expect `retry_err.max_retries` number of retries, after which the loop exits with the right reason.
* when initial or any consequent call to `self.provider.generate` throws a `RetriableError`, we expect the requested wait period is waited. You can introduce another parameter in `InteractionManager` to inject a waiter.
* when `self.provider.generate` results in tool calls, we expect the thinking session will continue.
* when `self.provider.generate` does not provide a finish_reason, we expect the thinking session will continue.
* when `self.provider.generate` does not throw and does not yield either tool calls or a reason to finish, the thinking session will continue for _DEFAULT_MAX_RETRIES attemts. In this scenario, if provider returns any assistant messages, they will all be stored in history.
* when initial or any consequent call to `self.provider.generate` or `self.tools.call_tool` throws any error, we expect that the provider and common history contain all previous turn messages, but not the failed conversation turn.
* when initial or any consequent call to `self.provider.generate` or `self.tools.call_tool` throws any non-retriable error, we expect the thinking session stops and the reason_to_finish contains a valid reason.
* when `RetriableError` does not specify `max_retries`, the default is used.
```

---

# Compact history

Prompt lost.

Result:

```
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
```

---

# Address a specific part of code, deep analyzis and refactoring ideas and goals.

Idea: identify parts with high cyclomatic complexity / high loc in function, find relevant tests, and run this prompt on it. 40 loc is more than enough for a function.

```
Take a look at @src/streetrace/ui/interaction_manager.py. This class is responsible for driving the main conversation loop. The process_prompt method seems to have a high cyclomatic complexity and a lot of flow control conditions.

Investigate the process_prompt in details and understand it's logic clearly. Research unit tests at @tests/ui/test_interaction_manager.py. Identify and describe key scenarios and control flow.

Can you suggest ideas for how to refactor `process_prompt` to reduce cyclomatic complexity, increase readability and maintainability in accordance with SOLID principles?
```

---

# Quick task

... (task description)

Please analyze current project structure and architecture, flowchart, data model, and coding style, and implement this new functionality.

When done, run `git status -u`, and check modified code using `git --no-pager diff HEAD`. Ensure that all new and modified code has a high unit test coverage using the new and modified tests. If coverage is missing, please create new tests to introduce directed atomic tests to increase coverage. Run new tests and iterate until they pass.

Finally, run static analysis to ensure the new code matches best practices and project standards.

# Requirements

Here is a task that we need to work on. Break it up into functional and non-functional requirements.
Identify if any obvious requirements are missing, and ensure the non-functional requirements meed necessary
quality goals.
Create an implementation plan for how to modify this project to complete the described task, keeping high maintainability and code quality. Do not introduce changes at this stage.

You will be penalized for reading the existing files at this stage, just leverage the provided information.

Task:

---
> ...
---

Save your analysis output in tasks/0001/10-Requirements.md.

---

# Approach

Please research the codebase of this project and read relevant files to and identify places relevant to the task described in @tasks/0001/10-Requirements.md.

Read only relevant files using the provided tools.

Clearly identify components that need to be changed or added to implement this feature, and explain what changes need to be made.

Provide a textual description of the required class diagram and data model changes relevant to this task.

Save your analysis output in tasks/0001/20-Approach.md.

---

# Flwochart

Please explain a step-by-step logic flow, similar to a textual flowchart, for a new task that we need to work on.

I have prepared an implementation approach summary that provides more context in @tasks/0001/20-Approach.md.

Task:

---
> ...
---

Please provide a step-by-step detailed textual flow chart for this feature and save it in tasks/0001/30-Flwochart.md.

---

# Ground rule scenarios

I am working on a new task described as follows:

---
> ...
---

I have summarized the requirements in @tasks/0001/10-Requirements.md.

Define a set of user scenarios that can be used as ground rules for testing this functionality when it's ready, and save it in tasks/0001/40-GroundRules.md.

---

# Ground rule tests

I am working on a new task described as follows:

---
> ...
---

I have summarized the requirements in @tasks/0001/10-Requirements.md, an implementation approach in @tasks/0001/20-Approach.md, and ground truth user scenarios in @tasks/0001/40-GroundRules.md.

Write a minimal set of unit tests to cover the ground rule scenarios, and implement the unit tests.
Also implement the necessary code stubs in accordance with the implementation approach to make these tests pass. Use mocks for interacting with system and external APIs. Make sure that implemented tests treat the system under test as black box to ensure we are only testing inputs and outputs, so we can re-use these tests in the next steps. Closely align these tests to the ground rule scenarios. Be careful with tests that can lead to infinite loops to avoid hanging tests.

Run the tests using `source venv/bin/activate && pytest tests/.../test_NEWLY_CREATED_TEST_FILE_NAME.py` and make sure they pass, or fail in a predictable way due to fake data and stub implementation.

Please list the created tests and stubs in tasks/0001/50-GroundRuleTests.md.

---

# Implementation

I am working on a new task described as follows:

---
> ...
---

I have summarized the implementation approach in the following files:

1. Requirements: @tasks/0001/10-Requirements.md
2. Implementation approach in @tasks/0001/20-Approach.md
3. A flowchart in @tasks/0001/30-Flwochart.md
4. Ground truth user scenarios in @tasks/0001/40-GroundRules.md
5. And also implemented some initial tests and stubs as explained in @tasks/0001/50-GroundRuleTests.md.

Please go ahead and implement the complete discussed solution.

Make sure to run the unit tests and iterate to make sure they pass.

Analyze the implementation and describe the implementation details in tasks/0001/60-Implementation.md.

---

# Review changes and explain if this satisfies the requirements

The original user's request was:

---
> ...
---

I've prepared a flowchart related to this feature in @tasks/0001/30-Flwochart.md, and implemented this feature describing my understanding in @tasks/0001/20-Approach.md, implementation in @tasks/0001/60-Implementation.md.

Please check all added and modified files using `git status -u`. For modified files, use `git --no-pager diff HEAD RELATIVE_FILE_PATH`. Throughly review the changes, and explain the modified logic in details.

Please find the critical parts of code that address the requirements.

Use your understanding of user's task and check if they meet the requirements and fulfill
the steps described in the flowchart.

Explain if this implementation fulfills the requirements and addresses the original user's request. Explain if anything is missing or wrong.

Save your analysis result in tasks/0001/70-Review.md

## Try just explaining

I have implemented a new feature. Please check all added and modified files using `git status -u`. For modified files, use `git --no-pager diff HEAD RELATIVE_FILE_PATH` to see what's changed in the file. Ignore tests and non-code changes. For code changes, explain them line by line and provide a summary for each added modified code block explaining the modification goal. Save your result in REVIEW_PREP.md.

gpt 4.1 and anthropic failed to describe the critical part.
gemini 2.5 explained it and I can see the bug by reading the explanation.
gpt o1 also explained it, a little more wordy but fuzzy

## Compare flowchart to this explanation

I have implemented a new feature explained in @SUMMARY.md. The original flowchart I prepared for this implementation is in @FLOWCHART.md. Please check the summary of all changes I've made in @REVIEW_PREP.md and see if all changes are valid and the implemented feature completely fulfills user's request. If it doesn't, please explain what's wrong or missing. Save your analysis result in INITIAL_REVIEW.md

Even with Gemini's explanation and the flowchart, no models can identify the bug.

# Coverage

Find newly added code and tests using `git status -u`, and check modified code using `git --no-pager diff HEAD`. Identify if the new and modified code has a high coverage using the new and modified tests. If coverage is missing, please create new tests to introduce directed atomic tests to increase coverage. Run new tests and iterate until they pass.

# Static analysis

Identify all added or modified files using `git status -u`. Run static analysis and tests on all added or modified source code files and fix all issues add missing code docs. Make sure to run python commands in venv, like this: `source venv/bin/activate && COMMAND`.

Save your analysis result in tasks/0001/80-StaticAnalysis.md

# Code review

The original user's request was:

---
> ...
---

Review the implemented code for quality and relevance of introduced changes, based on the given input. You can check the modified and added files using `git status -u`. Analyze if there are important issues with the reviewed code, such as potential bugs and security issues, high cyclomatic complexity, or low maintainability, and summarize your recommendations on further optimizations. Provide a short conclusion and suggestions on enhancing the code if necessary.

Save your analysis result in tasks/0001/90-FinalReview.md

---

# Workflow

Example story:

```
As a user, when I enter a `/compact` command, I want the whole conversation history to be summarized and replaced with a compact version reducing token count, but maintaining all goals and progress that was achieved during this conversation. After entering `/compact` I expect to be able to continue collaborating with the LLM maintaining the conversation flow, but removing all exccess data unrelated to this subject from the context.
```

Workflow:

1. **Requirements**
   Store the requirements
1. **Approach**
1. Summarize the result and store separately so we can re-write the history going forward.
2. **Ground rule scenarios**
   Store the scenarios.
3. **Ground rule tests**
   Store the test path / name.
3. **Implement**
   Summarize the implemented solution.
   Store the summary.
7. Iterate until the tests pass.
8. Review all changes and idenfity if they fulfill the original requirements
8. Implement additional tests to achieve high level of coverage for the new code.
9. **Code review**
9. **Static analysis**


---

# Story: /compact

```
As a user, when I enter a `/compact` command, I want the whole conversation history to be summarized and replaced with a compact version reducing token count, but maintaining all goals and progress that was achieved during this conversation. After entering `/compact` I expect to be able to continue collaborating with the LLM maintaining the conversation flow, but removing all exccess data unrelated to this subject from the context.
```

```
Summarize this conversation concisely in details, focusing on:
- The primary goals or tasks being worked on.
- Key decisions made and important information discovered.
- Progress made towards the goals.
- The current state and any immediate next steps or questions.
The summary should provide enough context for the AI assistant to seamlessly continue the conversation. Preserve the overall narrative flow. Retail paths to relevant files, and relevant code snippets that can be used in the further conversation.
Save the summary in the SUMMARY.md file and append the last line saying "Don't start the implementation yet, wait for further instructions."
```

```
What are the most important things we have discussed so far?
```

---

# Story: Save History

```
As a user, I want all my conversations stored in a local Markdown file so I can continue a past conversation with a model, or open it in a Markdown viewer. I also want to be able to edit the markdown and then continue the conversation with the edited version of the chat history.
```

# Huge tool outputs

E.g.

Step 1:

```
Run `poetry run ruff check src tests` and analyze the results: list all files that have issues with a list of errors and line numbers for each file. The result should look like this:


src/streetrace/FILE1:
   ERRCODE, line_number_of_first_occurance, line_number_of_next_occurance, ...: Description

src/streetrace/FILE2:
   ERRCODE, line_number_of_first_occurance: Description
   ERRCODE, line_number_of_first_occurance: Description


Save the result in ./tmp/lint.txt
```

Step 2:

```
/clear
```

Step 3:

```
See lint issues in @tmp/lint.txt and fix them. Run `make test` to make sure all tests are passing.
```

Thoughts:

* Can I have the model to manage the conv history keeping only what's needed?
* Can I run CLI right from the prompt to append the result to user messages?
* Can I pipe CLI results into model with additional instructions? If the pipe is not saved in history, then it gives me a way
  to quickly add CLI result summaries to history. E.g.:

  ```
  /cli: poetry run ruff check src tests | model "analyze the results: list all files that have issues with a list of errors and line numbers for each file. The result should look like this:


  src/streetrace/FILE1:
    ERRCODE, line_number_of_first_occurance, line_number_of_next_occurance, ...: Description

  src/streetrace/FILE2:
    ERRCODE, line_number_of_first_occurance: Description
    ERRCODE, line_number_of_first_occurance: Description"
  ```

  Adds the summarization result to history.


===

# Refactoring

```
Take a look at @src/streetrace/llm/llmapi.py. It has four implementations in src/streetrace/llm subfolders for anthropic, ollama, gemini, and openai. There are several issues with this interface:

1. It has a separate `initialize_client` function which returns a provider's type that is later used only in LLMAPI's own `generate` function. LLMAPI should encapsulate provider's implementation and hide it from callers, so the initialization should not return an instance of provider's implementation, instead it should be stored internally.

2. `generate` accepts `messages: ProviderHistory`, and instead it should accept `history: History` and LLMAPI implementations should convert it to the history format they need. It can optionally accept `messages: ProviderHistory` to avoid pointless conversions when used in @src/streetrace/interaction_manager.py state machine, and when it's not provided, it should require History.

3. I think it will be better if `manage_conversation_history` will also accept `history: History` instead of provider history, and convert it internally.

4. `generate`'s `system_message` and `tools` should be optional and skipped if not provided.

Please implement the refactoring and update related tests. When running tests, please run each test file separately to ensure we don't overload the context window.
```

The result is shitty code. It's alright in general, but it misses important files, some decisions
are arguable (in a bad way), etc. Need to try something like:

1. Smart RAG discovering what needs to be changed and feeding it to the model
2. Iterative thinking process to find different solutions, compare them, and find the right one
3. Implement
4. Review
5. Test

What's missing:

1. Smart RAG.
2. Workflows allowing arbitrary iterations.

===

# Tests

Please analyze the best strategy to break up the functionality into user scenarios, and create unit tests reflecting the user scenarios.

When creating tests, please make sure to create small and fast tests.

---

Run `git status` to see what's in progress right now. There are several tests failing, specifically in @tests/test_application.py, @tests/test_history_ manager.py, and @tests/test_interaction_manager.py. Please fix failing tests.

Remember, when running any python code, run with `poetry`, for example `poetry run pytest tests/test_application.py --timeout=5`.
When running pytest, always run a specific file or test, for example `poetry run pytest tests/test_history_manager.py --timeout=5`.
When running pytest, always set a timeout, for example `poetry run pytest tests/test_interaction_manager.py --timeout=5`.

All tests should pass in under 1 second, consider all tests that take longer failing and fix them.

===

# Refactoring

Take a look at @src/streetrace/application.py and files under src/streetrace/commands/. The user can type in commands and they get executed using command definitions. Right now all commands execute a predefined command in application.py. We need to move the command execution logic to the commands themselves.

Currently the commands use several properties of Application state, such as conversation_history, ui, interaction_manager, config, prompt_processor. In order to move the code into the commands implementation, we need to pass the necessary object instances directly to the commands that need them.

This is challenging because the CommandCompleter depends on the available_commands, PromptCompleter depends on the CommandCompleter, ConsoleUI dependson the PromptCompleter, and everything else depends on the UI.

I see several options to solve this:

a. We can initialize CommandCompleter with command names, and move the actual command instances creation until after everything else is initialized and right before the Application initialization.
b. We can decouple ConsoleUI from everything else via an event bus, and send all data to it using events/messages. As a result we will initialize the event bus, then PromptProcessor, InteractionManager, then create the Commands and give them instances of everything we need, and then initialize the Application as the last bit.

In all cases, we need to introduce some kind of history management that is separate from the Application and injected into all classes as a dependency.

What are the other options to achieve the goal?


# RAG approach

I want to enable LLM to be able to find where a certain feature is implemented and how it impacts the rest of the codebase.
 Ideally, I want to index the codebase so the LLM can search the index and find relevant code locations. Assuming the user continuously uses similar vocabulary,
 and the code is well documented, I want the model to call a tool providing relevant keywords, and find all places in code relevant to this feature.

For example, I have a web-app that implements a todo list. When I say "Add category labels to todo lists", the model calls a tool:

```
find_feature(keywords=["todo item", "category", "add todo item", "update todo item", "remove todo item"])
```

The tool needs to respond with all necessary information about all source and documentation files found in the codebase relevant to the requested feature, so LLM can use this information to understand how to implement the feature.

How to implement a tool like that?

Just share a proposal, don't start implementing yet.

Answer as an expert in the area, then act as a third-party expert in the area, assess the proposal, critique and provide feedback. Finally, merge both to share your conclusion.


# mcp (brainstorm template)

```
Let's brainstorm how we can add MCP capabilities to the project. In general, I want StreetRace to implement an MCP client and allow the user to easily
configure any MCP servers/providers they want to make available to Streetrace.
Please brainstorm as a team of experts in the area, and provide a final report on the approach. Then critique as a third-party expert in the area. Prov
ide a merged result.
```

The idea behind all these prompting patterns is to enable one or another way for thinking through the problem, instead of coming to conclusion immediately.
Humans can also do that. We usually jump to conclusions as that's how our brain functions - it loves answering questions. But there are frameworks that help
manage this behavior. E.g., five whys help oneself identify core reasons of something, similar to how ATAM helps one come up with a structured tradeoffs
analysis, or TOGAF helps to create solid system architectures.

Some quick examples:

1. Think step by step.
2. Answer as one expert. Then critique as another.
3. Define a team of experts, and brainstorm this with the team.
4. Follow an ATAM process to evaluate.


====

Create a python app that has three running modes each of which implements the following:

# 1. Downloader

Downloads the latest english-language wikipedia dump (from a mirror if there is a mirror close to Seattle, WA) and saves it in the `./data` directory.

# 2. Parser

1. Reads the wikipedia dump from a location indicated in the '--dump' argument and unpacks it.
3. Parses it to find all articles about people, locations, and redirects (see details below).
4. Stores the extracted data in local csv files (e.g., persons.csv, locations.csv, redirects.csv).

At this step, the parser extracts all fields as text keeping creole formatting, i.e. `[[` and `]]`, etc.

## Extracting people

When extracting people, make sure to extract both living and deceased people.

Fields to extract:

- Wikipedia page title (the page name that goes into the URL),
- Infobox tags `full_name`, `full name`, `name`, `birth_date`, `birth_place`),
- Infobox type (e.g. extract "royalty" from `{{Infobox royalty`),
- Short description tag (for example extract "Spiritual leader of Tibet since 1940" from `{{Short description|Spiritual leader of Tibet since 1940}}`),

Either 'Short description' or 'Infobox type', and either the `birth_date` or `birth_place` are required. For example, if 'Infobox type' and `birth_place` are extracted, the record is valid. If `birth_date` and `birth_place` of birth are extracted, but neither 'Short description' nor 'Infobox type' are extracted, log a warning providing the page title, and treat the record invalid.

The easiest possible way to detect if a page is a person page is to use the required attributes.

Save extracted records in `./data/people_raw.csv`.

## Extracting locations

We need to extract all location pages to allow mapping people's places of birth to lat and lon coordinates.

Fields to extract:

- Wikipedia page title (the page name that goes into the URL),
- Coordinates (extract from the first occurance of the `coord` tag, for example `{{coord|36|22|41.1|N|101|51|57.2|E|region:CN-63|display=it}}`)

Save extracted records in `./data/locations.csv`.

## Extracting redirects

We need to extract all redirects so we can find all possible redirects to all the location pages.

Fields to extract:

- Wikipedia page title (the page name that goes into the URL),
- The redirect page (from the `#REDIRECT` tag, for example extract "Timur" from `#REDIRECT [[Timur]]`)

Save extracted records in `./data/redirects.csv`.

## General notes on extracting data

Read, extract, and save data in a streaming pipeline. Never store lists of extracted records in memory before saving.

All Wikipedia tags are case insensitive, i.e. `Infobox` is the same as `infobox` and the same as `INFOBOX`.

Use python's csv module to write and read csv.

# 2. Process data

The goal of this step is to cleanup and validate people data.

Read the redirects and locations, building a single dictionary mapping of lowercase names to coordinates. The coordinates should be parsed from Wikipedia format (`{{coord|36|22|41.1|N|101|51|57.2|E...}}` to decimal lat and lon coordinates). The dictionary will map all names (including redirects) to the coordinates.

For example, if we have a location 'Shahrisabz' pointing to '39° 3′ 0″ N, 66° 50′ 0″ E', and a redirect 'Kesh' redirecting to 'Shahrisabz', the dictionary will have two records:

```
{
  'Shahrisabz': (39.05, 66.833333),
  'Kesh': (39.05, 66.833333),
}
```

Then process the people dump (`./data/people_raw.csv`) in a streaming pipeline:

1. Wikipedia page title (the page name that goes into the URL),
2. Extract person's name from one of the fields, in order of priority: `full_name`, `full name`, `name`, page title. Remove HTML comments and all contens of any HTML tags, just keep plain text.
3. Extract birth date from `birth_date`. We need the fullest possible date available in a form of json object like `{'y': 1900, 'm': 3, d: 10}` where both month and day are zero bound. For example:
  - '{{birth date and age|1957|7|24|df=y}}' extracts as `{'y': 1957, 'm': 6, d: 23}`
  - '1320s' extracts as `{'y': 1320}`
  - '20 or 21 July 356 BC' extracts as `{'y': -356, 'm': 6, d: 20}`
  - '{{circa|980}}' extracts as `{'y': 980}`
4. Extract person's birth location by taking all links from `birth_place` and looking them up in the name to coordinates mapping we've built before. The first location that was possible to map in the order the locations appear in the `birth_place` field wins. For example, if the `birth_place` = "Perhaps [[Transoxiana]], or eastern [[Uzbekistan]]", try looking up 'Transoxiana' in the location directory, which will fail, then try 'Uzbekistan' and use the identified coordinates.
5. Extract occupation as plain value from one of the fields, in order of priority: 'Short description' or 'Infobox type'

Save the output in `./data/people.csv`.

Occupation and either date or place of birth are required.

Examples of resulting records:

```
wiki_link,name,birth_date,birth_place,occupation
"Shavkat Mirziyoyev","Shavkat Mirziyoyev","{'y': 1957, 'm': 6, d: 23}","(39.96, 68.379)","President of Uzbekistan since 2016"
"Timur","Shuja-ud-din Timur","{'y': 1320}","(39.05, 66.833333)","Turco-Mongol conqueror (1320s–1405)"
```

## General notes on processing data

Read, extract, and save data in a streaming pipeline.

Use python's csv module to write and read csv.

# 2. Trainer

Loads the `./data/people.csv` file and trains a classifier with the provided data. The classifier should predict occupation given place and date of birth. The trained model should be saved in the current directory.

## Location

Ensure that if the lat/lon are close, they provide a close match.

## Dates

Year is unimportant, and if Month+Day are close, they provide a close match.

## Occupation

Given that occupation is a free form text, we need to run clustering before encoding occupation.

Use SentenceTransformers to create semantic vectors from all distinct occupations, run K-Means clustering estimating n_clusters = 1/10 of the number of distinct occupations, and use the cluster number as the occupation value for training. Save the clustering results (original occupation text and cluster number) in `./data/occupation_clusters.csv`.

# 3. Predictor

Takes place and day and month of birth, translates the place of birth to lat/lon coordinates, and uses the model to predict occupation.

===

In the @parser.py `_process_content` function, where we extract person data, let's first extract the full in fobox with all of its attributes (including the type), and then lookup its properties.

Specifically, lets create a new function called _extract_first_infobox that will accept `content` and return a dict[str,str]. _extract_first_infobox will find the first full infobox in the article (`{{infobox ... }}`) and parse it extracting all properties and their values.

I believe, to address that, we need to create a state machine that can consume full quoted and parenthesised chunks of text. If we treat the infobox syntax as {{infobox name | property=value | property=value | .. }}, then we should follow this process to parse it properly:

Find a start of the infobox (`{{infobox`)
Read text chunk until the next free `|` and consider it infobox type, stripping whitespace. The infobox type can be stored in the "_type_" key of the dict.
If we see |, read the next full chunk until we see a free `=` and consider it a property name.
Read the next full chunk until we see `}}` or `|`. If we see `}}` we consider infobox read successfuly. If we see `|`, we go back to reading property name.

"full chunk" means a chunk of text with all the valid quotes, braces, braces, or `<` and `>` signs.
"free `=`" or "free `|`" means `=` or `|` that does not belong to any previous text chunk.
Keep in mind that a single quote (` or ') is a part of a word, unless it's a '' (double single quote) which denotes a double quote in wikipedia.

Also create a helper function that takes text content as an input, uses _extract_first_infobox, and pretty prints the infobox, so I can test with various fancy articles.

===

Third party code (google-adk):

session.py: @.venv/lib/python3.12/site-packages/google/adk/sessions/session.py
event.py: @.venv/lib/python3.12/site-packages/google/adk/events/event.py

---

Session object serialized as json: @tests/test_session_service.py.json

---

Expected markdown document: @tests/test_session_service.py.md

---

Implement the code in @src/streetrace/session_service.py

---

Implement tests in @tests/test_session_service.py

---

Please implement methods in `MDSessionSerializer`. Deduct the fields mapping from the provided json and markdown examples. Note that `events[].content.parts[].text` is external data, so valid markdown is not guaranteed. Use marko to convert the external markdown to AST before adding to the serialized document.

When serializing, a better approach will be to build an AST of a complete document, and then render it to markdown. When deserializing, it seems best to parse markdown to AST, then create a dict and use model_validate to create the Session object.

For markdown format, don't add any markers or front matter. Rely on the following facts:

* Heading-1 ('#') is always the session-level info
* `## App State` header contains data from Session.app_state
* `## User State` header contains data from Session.user_state
* `## Events` header contains the full Session.events list
* Inside `## Events`, Heading-3 (`###`) defines the author of the message. There are two possible authors: the user (Session.user_id), and the app (Session.app_name). Consequent similar authors are skipped when rendering.
* When deserializing, if can't extract the timestamp due to missing Heading-3, don't fill it in.
* `#### call: $NAME` header specifies the 'function_call' field
* `#### response: $NAME` header specifies the 'function_response' field

Also, please implement tests covering the functionality using the existing example files (test_session_service.py.json and test_session_service.py.md).

Add docstring comments in src/streetrace/session_service.py where missing.

Review and critique the implementation as a third-party engineer, and fix the code based on feedback.

Analyze the final implementation and provide feedback on what's missing, what are the pitfalls, and important missing test cases.

===

Analyze the requirements and understand the goal. Come up several approaches to reach the goal. List the trade-offs of each approach. Review the approaches and critique as a software engineer. Choose and propose the best approach. Provide a short description of each approach, and a detailed description of the proposed approach.
