import yaml
from streetrace.agents.yaml_models import YamlAgentSpec

STREETRACE_CONFIG = """
name: StreetRace_Agent
description: A generic agent that can be configured with different tools and sub-agents.
instruction: You are a helpful assistant.
tools:
  - streetrace:
      module: "my_module"
      function: "my_function"
sub_agents:
  - $ref: "path/to/another_agent.yml"
"""

ADK_CONFIG = """
name: ADK_Agent
description: An agent configured in the ADK format.
instruction: You are a helpful assistant.
tools:
  - tool_code: "code_writer"
    fallback_instructions: "Use this tool to write code."
  - agent: "another_agent"
"""

def test_parses_streetrace_config():
    data = yaml.safe_load(STREETRACE_CONFIG)
    spec = YamlAgentSpec(**data)
    assert spec.name == "StreetRace_Agent"
    assert len(spec.tools) == 1
    assert len(spec.sub_agents) == 1

def test_parses_adk_config():
    data = yaml.safe_load(ADK_CONFIG)
    spec = YamlAgentSpec(**data)
    assert spec.name == "ADK_Agent"
    assert len(spec.tools) == 2
