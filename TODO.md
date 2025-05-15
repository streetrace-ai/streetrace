# todo

## 2025-04-29

To make this a real tool, I need to:

    1. Use an LLM gateway to access LLMs, e.g. https://github.com/BerriAI/litellm
    2. How does StreetRace relate to benefit from a2a? Perhaps run as a Server exposing agents? Allow connecting to other agent providers and run them as a client?
    3. Use MCP for all context, allow adding new MCP providers and implement a set of default tools, e.g. local files
    4. The user can define their custom agents and tools.
    5. Run all ReAct sequences as Actors. Find if we can use llama index, or find a lightweight actor model framework. Pyakka looks cool, but it seems too tightly coupled to threading, which is not the point I'm looking for.
    5. Show an example of leveraging coding agents with this, e.g. https://github.com/noahshinn/reflexion, https://github.com/alekst23/creo-cortex
    6. Show an example of implementing a full eng workflow from requirements to tests, perfect code, docs, etc.

### release:

- [ ] cleanup logs
- [ ] update readme
- [ ] mcp integration

### todo

- [ ] identify all features of interaction manager and confirm in adk implementation
    - [ ] count tokens: check if tokens are stored in session
    - [ ] fix status progress
    - [ ] show request tokens, costs, session tokens and costs, daily/monthly etc.
    - [ ] PAIN cost management - show request cost, session cost, and set limits / quotas / budgets
    - [ ] PAIN Show total token count in this chat session in status bar
- [ ] code execution
- [ ] break up new features into tasks (see email)
- [ ] fix tests
- [ ] how to manage history?
    - [ ] maintain conversation history over restarts,
    - [ ] don't keep old files in history
    - [ ] show files already in context over the prompt
    - [x] Add turn summary to session instead of full contents.
    - [ ] compact and cleanup session
- [ ] imports performance
- [ ] PAIN add cli timeout to avoid hanging commands, report timeout to the model.
- [ ] count request tokens before the request is sent, and show it separately.

- [ ] Prompt history
- [ ] langchain tools
- [ ] mcp tools with sse
- [ ] Integrate MCP prompts as slash-commands.
- [ ] add last modification date to read/write_file to check if it's overwriting a newer version.
- [ ] print available backends and model names
- [ ] use logprobs to output model confidence
- [ ] When the model runs python interpreter as a tool, Ctrl+C hands the app
- [ ] When the model runs python interpreter as a tool, the user cannot see what they are typing
- [ ] support @last conversation
- [ ] @mentions should support folders
- [ ] prompt templates
- [ ] web ui that works on your repo in the background, so you can work on the go
- [ ] If gemini responds with malformed tools or other model errors, feed it back so it can fix its own error
- [ ] add datetime to Message
- [ ] usage stats
- [ ] google.genai.errors.ServerError: 500 INTERNAL. {'error': {'code': 500, 'message': 'An internal error has occurred. Please retry or report
- [ ] run cli in background
- [ ] Add command to summarize work done and store it in worklog from the user scenario perspective, as in "what's new"?
- [ ] read_file, when the file is missing, see if it's somewhere around and return "did you mean"
- [ ] cli command validation (e.g., can configure regex in agent or streetrace config file)


### done

- [x] event-driven ui
- [x] estimate token count while typing the prompt
- [x] print working directory
- [x] Ctrl+C isn't working alright
- [x] Local tool definition is suboptimal
- [x] Add turn summary to history instead of full contents.
- [x] re-think tools
- [x] test order of messages when user input contains mentions (does it matter if a mention is before or after the prompt?)
- [x] context (read from ./streetrace files) and file mentions are two different things and should be processed separately.
- [x] attach context mentions after the prompt, not before
- [x] experiment with diff outputs, it's ugly
- [x] param to retry litellm.InternalServerError, e.g. AnthropicError - {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}
- [x] get real agent working
- [x] integrate with adk
- [x] refactor all app wiring logic (main, app, etc)
- [x] retry logic for litellm interface
- [x] get fake agent working with fake tools
- [x] get fake agent working with mcp tools
- [x] based on agent request, load only available tools
- [x] get fake agent working with function tools
- [x] use llm gateway
- [x] history is not saved when err 500 in gemnini
- [x] pypi publishing
- [x] Anthropic errors out. Context is not added. Format is also not correct.
- [x] Context is not added, and unit tests don't fail.
- [x] for streamed responses, collect all text into one message
- [x] fix unit tests, lint, etc
- [x] Show token counts
- [x] Prompting UI
- [x] context size management
- [x] --type retry to retry-- Press Enter to retry
- [x] How to use other models on vertexai
- [x] create console print module so it uses the proper colors
- [x] count input/output tokens consumed
- [x] _generate_with_tools needs to return finish reason
- [x] anthropic api 529 overloaded
- [x] text editor
- [x] Handle retryable API errors:
        * HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.anthropic.com/v1/messages'
- [x] compact history command
- [x] summarize task command (Summarize this conversation describing the goal and outcomes. Mention paths to all files included in this context.)
- [x] create an ollama implementation similar to gemini and anthropic
- [x] create an openai implementation similar to gemini and anthropic
- [x] common interface
- [x] make rel paths relative to work dir
- [x] stdio mapping
- [x] function response will be printed to the chat, but it has to be pretty, e.g. diff for the write operation.
- [x] also add space between message and function name
- [x] @mention files and folders


### ideas

- [ ] It would be great to allow in-code documentation to be sent as context.
- [ ] Keep only cli
- [ ] Bootstrapping and "Build context" mode:
    - [ ] Discover project rules and recommendations
    - [ ] Describe project structure and document each file
    - [ ] Code review
    - [ ] Describe code health pipeline, confirm if all the necessary tools are configured
    - [ ] Auto add readme and context to the conversation history
- [ ] Law of robotics

## thoughts

### linting, unit tests, etc.

There seem to be to things:

1. Something that has be done related to specific changes.
    E.g., implement new tests.
2. Something that has to be done for all changes.
    E.g., run all tests and static analysis.

For all changes, there has to be a feedback loop with the model itself before it completes. So we should make
sure the model finishes any task with running a pre-release pipeline involving all checks, and address all issues.
Ideas:

1. Tell the model to do so.
   Technically we mention it in the current system instructions, but it doesn't always do it, and even if it
   does - it can do it in a different way every time.
2. Add a tool that runs pre-release checks.
   Solid for a project, but not applicable for street-race as a more common tool.


### Console status

We need to inform the user about current processing stats and costs:

1. When typing a prompt in ConsoleUI.prompt_async (see @src/streetrace/ui/console_ui.py) -> we need to show the estimated number of tokens in the typed prompt in rprompt.
2. During the turn -> Turn tokens in status update. (supervisor)
3. When typing -> total tokens and cost of the current session. (console_ui -> app -> console_ui)

What if I load yesterday's session? Totals will show cumulative for the loaded session.


#### Show the estimated number of tokens when typing

> **_DONE_**

Create a class called TokenEstimator in @src/streetrace/llm_interface.py. Initialize it with an instance of AdkLiteLlmInterface and provide one method: `estimate_token_count(input: str) -> int`. Keep it a stub returning 42. In @src/streetrace/app.py `create_app`, create an instance of this class and pass its reference to the ConsoleUI.

In ConsoleUI's `prompt_async`, we need to pass in a validator parameter into `prompt_session.prompt_async` call. The validator

#### Bits and pieces

1. We need to get the usage and costs data from litellm in llm_interface.

#### Updating UI

> **_DONE_**

TokenEstimatingValidator depends on LlmInterrface -> obvious
LlmInterrface depends on ConsoleUI -> this is the reverse dependency.
ConsoleUI depends on TokenEstimatingValidator -> half-bad. Ideally we'd want all changes to the ui to happen through the ui_bus.

UI is different from other components:

There is the App that does something.
There is the UI, and its sole purpose is to communicate with the user.

UI will display info produced by other components (push)
UI might *request* info from other components (pull)

So there is a natural two-way dependency causing deadlocks.

This is not essential though. If we have a "State", then components and the UI will update the state, and subscribe to state updates, so there is no interdependency.