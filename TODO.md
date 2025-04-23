# todo

## release:

- [ ] cleanup logs
- [x] history is not saved when err 500 in gemnini
- [ ] pip publishing
- [ ] update readme

## other

- [ ] project rules (like activate venv for any bash session)
- [x] for streamed responses, collect all text into one message
- [ ] fix unit tests, lint, etc
- [ ] Prompt history
- [x] Show token counts
- [ ] Show total token count in this chat session in status bar
- [ ] maintain conversation history over restarts,
- [ ] show files already in context over the prompt
- [x] Prompting UI
- [ ] context size management
- [ ] support @last conversation
- [ ] @mentions should support folders
- [ ] prompt templates
- [ ] web ui that works on your repo in the background, so you can work on the go
- [x] --type retry to retry-- Press Enter to retry
- [ ] How to use other models on vertexai
- [ ] If gemini responds with malformed tools or other model errors, feed it back so it can fix its own error
- [ ] add datetime to Message
- [x] create console print module so it uses the proper colors
- [x] count input/output tokens consumed
- [ ] usage stats
- [x] _generate_with_tools needs to return finish reason
- [ ] anthropic api 529 overloaded
- [ ] text editor
- [ ] Handle retryable API errors:
        * HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.anthropic.com/v1/messages'
- [ ] google.genai.errors.ServerError: 500 INTERNAL. {'error': {'code': 500, 'message': 'An internal error has occurred. Please retry or report
- [ ] run cli in background
- [ ] Add turn summary to history instead of full contents. Add command to summarize work done and store it in worklog from the user scenario perspective, as in "what's new"?


## done

- [x] create an ollama implementation similar to gemini and claude
- [x] create an openai implementation similar to gemini and claude
- [x] common interface
- [x] make rel paths relative to work dir
- [x] stdio mapping
- [x] function response will be printed to the chat, but it has to be pretty, e.g. diff for the write operation.
- [x] also add space between message and function name
- [x] @mention files and folders


## ideas

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
