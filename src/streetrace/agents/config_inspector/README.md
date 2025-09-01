# Config inspector agent

A safety-first agent that inspects Kubernetes and infrastructure-as-code changes before they reach production. It helps prevent outages by validating configuration changes, analyzing past incidents, and surfacing risks so engineers can deploy with confidence.

## Capabilities

- Validate YAML syntax & semantics. Ensures Kubernetes manifests and config files are structurally valid and conform to API schemas.
- Detect risky changes. Compares changes (before/after) to highlight potential issues such as removed probes, reduced resource limits, or missing disruption budgets.
- Blast-radius analysis. Builds a dependency graph of services (Kubernetes, Kafka, microservices) and checks which downstream systems could be affected by the change.
- Leverage historical incidents. Mines incident records, configuration history, and postmortems to correlate similar past failures with the proposed change.
- Surface stability hypotheses. Generates predictions about the potential system impact (e.g., “likely to increase error rate under load”) and presents them for human confirmation.
- Human-in-the-loop safeguard. Posts findings as annotations in pull requests or CI/CD pipelines, allowing maintainers to approve, reject, or request a canary rollout before deployment.

## Usage

This agent can be used with the `run_agent` tool:

```python
run_agent(agent_name="Config inspector", input_text="Hi, please analyse PR with changes")
```

Or directly through the AgentManager:

```python
async with agent_manager.create_agent("Config inspector") as agent:
    # Use the agent
```

## Implementation

The Config Inspector agent implements the `StreetRaceAgent` interface, which requires:

1. `get_agent_card()` - Provides metadata about the agent
2. `get_required_tools()` - Lists the tools needed by the agent
3. `create_agent()` - Creates the actual agent instance

It also provides a legacy implementation through the `get_agent_metadata()` and `run_agent()` functions for backward compatibility.

## Development

This agent serves as a template for creating new agents. You can copy this directory and modify it to create your own agents.