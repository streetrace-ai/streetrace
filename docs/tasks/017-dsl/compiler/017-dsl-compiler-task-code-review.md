## Expectation 1:

./agents/*.sr agents use exactly similar tool configurations as their matching ./agents/*.yml definitions.

## Expectation 2:

**Act**:

Run `poetry run streetrace --agent agents/generic.sr --prompt="describe this repo"`

**Assert**:

Agent defined tools are loaded: streetrace.fs, github mcp, context7 mcp via tool provider.

## Expectation 3:

**Act**:

Run `poetry run streetrace --agent agents/generic.sr --prompt="describe this repo"`

**Assert**:

The agent uses the defined tools (streetrace.fs, github mcp, context7 mcp) to explore the current directory. The tools actually execute and return results.

For comparison (expected result) run `poetry run streetrace --agent agents/generic.yml --prompt="describe this repo" --model=anthropic/claude-sonnet-4-5` to see the working agent performance.

## Expectation 4:

**Arrange**:

Use agent definition agents/examples/dsl/specific_model.sr.

**Act**:

Run `poetry run streetrace --agent agents/examples/dsl/specific_model.sr --prompt="describe this repo"`

**Assert**:

The root agent runs with model `anthropic/claude-sonnet-4-5` as specified in `prompt greeting`

## Expectation 5:

src/streetrace/agents/dsl_agent_loader.py should load agent as defined in DSL. For example:

```
agent:
    tools fs
    instruction main_abc
    retry default
    timeout default
```

Should instantiate the agent with `fs` tools, `main_abc` instruction, exactly as configured. There is no room for guessing by looking up prompts by keyword matching or introducing default instructions as implemented now.

## Expectation 6:

The model the agent uses has to be specified in the intruction prompt in DSL. If not, we can look for the model with a special name "main" in DSL. If a model is explicitly provided in CLI args, it overrides everything. There is no room for guessing picking up "the first available model" as implemented now.

## Expectation 7:

Please scan the changes in this branch and find all new comments that mention "not yet fully implemented", "simplified for now". Analyze what the target implementation should be based on the design docs, and close the gap.

## Expectation 8:

--no-comments flag should remove comments from output.

## Expectation 9:

Agents without instruction should trigger E0010

## Expectation 10:

Indentation errors should use E0008

## Expectation 11:

**Arrange:**

Update the flow example by passing the user prompt to to the main_agent in the flow body.

**Act:**

Run `poetry run streetrace --agent agents/examples/dsl/flow.sr --prompt="describe this repo"`

**Assert:**

agents/examples/dsl/flow.sr should **actually** use flows as shown in user docs. Analyze the implementation gap with flows and fix them. The expected behavior is that the DSL will produce a python method body implementing the flow.

In general, the currently implemented separation of running "simple agents" vs. "flows" is a critical bug. The `DslAgentWorkflow` should define a single async generator function that executes the given (or the only, or the default) flow. The generated python code should define an abstract async generator function that executes the corresponding flow.

The method should implement the agent configurations by leveraging Google ADK agent types (research https://google.github.io/adk-docs/agents/multi-agents/) by running all agents as defined in the flow configuration the way they are defined, yielding events from agents.

In many cases, there can be several agents executed one after another each consuming the output of previous, in which case we can leverage ADK Sequental agents.

In many cases, there can be some data processing in between agent calls in the flow, in which case we should implement two agent runs with the defined data transformations in between.

See these examples:

**DSL:**

```
model analyzer = anthropic/claude-opus-4-5
model summarizer = anthropic/claude-sonnet-4-5

tool fs = builtin streetrace.fs

prompt summarize_prompt using model "summarizer": """Summarize the analysis results into a final report. Highlight critical issues and provide recommendations."""

prompt agent using model "analyzer": """Research this repository, find all *.sr files and analyze their contents."""

agent summarizer:
    tools fs
    instruction summarize_prompt
    description "Summarizes analysis results"

agent main_agent:
    tools fs
    instruction agent

flow process_document:
    $analysis = run agent main_agent
    $validated = run agent summarizer $analysis
    return $validated
```

**Generated python (partial):**

```python
async def flow_process_document():
    initial_prompt = ...  # Obtain the initial prompt or document to process
    adk_agent = SequentialAgent(
        name="flow_process_document",
        # create_agent should be implemented in the DslAgentWorkflow and implement
        # proper agent config discovery and LlmAgent instantiation (src/streetrace/agents/dsl_agent_loader.py)
        sub_agents=[create_agent(main_agent), create_agent(summarizer_agent)],
    )
    # run_root_adk_agent should be implemented in the DslAgentWorkflow
    # and implement the steps necessary to run the agent (see src/streetrace/workflow/supervisor.py)
    return run_root_adk_agent(adk_agent, initial_prompt)
```

---

**DSL:**

```
model analyzer = anthropic/claude-opus-4-5
model summarizer = anthropic/claude-sonnet-4-5

tool fs = builtin streetrace.fs

schema TaskAnalysis:
    items: list[string]

prompt summarize_prompt using model "summarizer": """Summarize the analysis results into a final report. Highlight critical issues and provide recommendations."""

prompt agent using model "analyzer" expecting TaskAnalysis: """Research this repository, find all *.sr files and analyze their contents."""

agent summarizer:
    tools fs
    instruction summarize_prompt
    description "Summarizes analysis results"

agent main_agent:
    tools fs
    instruction agent

flow process_document:
    $analysis = run agent main_agent
    $validated = run agent summarizer $analysis.items[0]
    return $validated
```

**Generated python:**

Assume

```python
async def flow_process_document():
    initial_prompt = ...  # Obtain the initial prompt or document to process
    async for event in run_root_adk_agent(create_agent(main_agent), initial_prompt):
        if event.is_final_response():
            # here we expect the final response data had already been validated and
            # trandformed to the expected TaskAnalysis model
            analysis = event.data
        yield event
    async for event in run_root_adk_agent(create_agent(summarizer_agent), analysis):
        yield event
```

---

## Expectation 12:

Analyze docs/user/dsl/getting-started.md and identify all "Known Limitations". Find corresponding feature definitions in the design doc. All those features should be implemented.