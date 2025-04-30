def main():
    """TODO:
    1. Use an LLM gateway to access LLMs, e.g. https://github.com/BerriAI/litellm
    2. See how we can benefit from a2a to define tools. Perhaps run as a Server exposing agents?
    3. Use MCP for all context, allow adding new MCP providers and implement a set of default tools, e.g. local files
    4. The user can define their custom agents and tools.
    5. Run all ReAct sequences as Actors. Find if we can use llama index, or find a lightweight actor model framework. Pyakka looks cool, but it seems too tightly coupled to threading, which is not the point I'm looking for.
    5. Show an example of leveraging coding agents with this, e.g. https://github.com/noahshinn/reflexion, https://github.com/alekst23/creo-cortex
    6. Show an example of implementing a full eng workflow from requirements to tests, perfect code, docs, etc.
    """


if __name__ == "__main__":
    main()
