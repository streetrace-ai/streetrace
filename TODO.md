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

- [ ] param to retry litellm.InternalServerError, e.g. AnthropicError - {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}
- [ ] context (read from ./streetrace files) and file mentions are two different things and should be processed separately.
- [ ] experiment with diff outputs, it's ugly
- [ ] add creation and modification dates to list/read files
- [ ] add last modification date to write_file to check if it's overwriting a newer version.
- [ ] test order of messages when user input contains mentions (does it matter if a mention is before or after the prompt?)
- [ ] attach context mentions after the prompt, not before
- [ ] print available backends and model names
- [ ] PAIN smart history management. Don't keep files that have been re-read or re-written, summarize chains of commands.
- [ ] PAIN cost management - show request cost, session cost, and set limits / quotas / budgets
- [ ] PAIN add cli timeout to avoid hanging commands, report timeout to the model.
- [ ] PAIN Show total token count in this chat session in status bar
- [ ] use logprobs to output model confidence
- [ ] re-think tools
- [ ] count request tokens before the request is sent, and show it separately.
- [ ] When the model runs python interpreter as a tool, Ctrl+C hands the app
- [ ] When the model runs python interpreter as a tool, the user cannot see what they are typing
- [ ] Prompt history
- [ ] maintain conversation history over restarts,
- [ ] show files already in context over the prompt
- [ ] support @last conversation
- [ ] @mentions should support folders
- [ ] prompt templates
- [ ] web ui that works on your repo in the background, so you can work on the go
- [ ] If gemini responds with malformed tools or other model errors, feed it back so it can fix its own error
- [ ] add datetime to Message
- [ ] usage stats
- [ ] google.genai.errors.ServerError: 500 INTERNAL. {'error': {'code': 500, 'message': 'An internal error has occurred. Please retry or report
- [ ] run cli in background
- [ ] Add turn summary to history instead of full contents.
- [ ] Add command to summarize work done and store it in worklog from the user scenario perspective, as in "what's new"?
- [ ] read_file, when the file is missing, see if it's somewhere around and return "did you mean"
- [ ] cli command validation (e.g., can configure regex in agent or streetrace config file)


### done

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
