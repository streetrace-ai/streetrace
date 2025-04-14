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

In @app/application.py there is conversation history object for both interactive and non-interactive mode. Let's implement conversation history management over app restarts. The conversations have to store the entire history, and every turn has to indicate the backend and model used for this turn. Each conversation history will have an ID generaged as YYYYMMDD_HHmmUTC, and the file name for the conversation has to match its id. We need to implement another optional command line argument to specify the conversation history (applicable to both interactive and non-interactive modes). If the argument is specified, the history needs to be hydrated from the referenced history. Let's store the history as markdown files that look nice when rendered, but include special macros that we can use when parsing and saving to allow parsing as a proper history. Describe the alternative approaches. Keep asking questions to clarify requirements before starting to implement.

Let's use YYYYMMDD_HHmmSSUTC for the ID. The history needs to be stored in .history folder within the current directory. If the invalid history ID is provided by the user, we should immediately error out and exit. We should save the frequency when the user enters a new message, and when the processing of assistant's message is complete. For the mentions, let's not differentiate between mentions and user messages, they should be stored in the history just the same way as the rest of the history. The big advantage of storing in mardown is that user can immediately render the result, use a markdown editor to edit it, etc., so it provides significant advantages.