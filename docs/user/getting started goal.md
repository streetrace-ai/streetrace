Getting started guide should focus on this workflow aiming to take the user through all the steps in 5 minutes:

```bash
# 1. Install streetrace from PyPI
$> pip install streetrace
# 2. Create a directory for your project and navigate into it
$> mkdir my_dir
$> cd my_dir
# 3. add keys to .env
# ANTHROPIC_API_KEY=your_anthropic_api_key
# GEMINI_API_KEY=your_gemini_api_key
# 4. See available agents
$> streetrace --list_agents
# 5. Create a custom agent (using the default Streetrace agent to generate DSL):
$> streetrace "Create an agent that writes a change request spec based on a user request. The agent should explore the codebase, find relevant docs and code pointers, then research the web and find the latest relevant whitepapers, community discussions, and articles. Then it should store the spec in ./docs/spec/ with a new spec ID. The spec should contain only the spec and findings, not the actual code."
... New agent created as "spec_writer"
$> streetrace --agent "spec_writer" "we need to add task planning tools to the built-in tools"
... ./docs/spec/123-task-planning-tools.md created.
```

After that, getting started should:
1. Walk through the agent DSL auto-created in the process above (where to find the DSL)
2. How to run it in GitHub Action (hint: using `../github-action`). Show a GitHub action workflow template that triggers on issue comment, run the "spec_writer" agent to create the spec based on GitHub Issue, and posts the spec as a comment using this new agent.
2. Run streetrace in Docker (hint: using `../streetrace-ai-docker`)