# DSL Agentic Patterns ADK Integration - Phase 5: Integration Tests

## Overview

Create integration tests that verify the full pipeline from DSL source to ADK agent creation for the agentic patterns (delegate and use keywords).

## Links

- Design document: `docs/rfc/017-streetrace-dsl.md`
- Related unit tests: `tests/unit/agents/test_dsl_agent_adk_integration.py`
- DSL agent loader: `src/streetrace/agents/dsl_agent_loader.py`

## Key Implementation Requirements

1. **Coordinator Pattern (delegate keyword)**
   - Parse DSL with `delegate to` clause
   - Verify sub_agents list is populated on LlmAgent
   - Verify sub-agents are created with correct tools and instructions

2. **Hierarchical Pattern (use keyword)**
   - Parse DSL with `use` clause
   - Verify AgentTool wrappers are added to tools list
   - Verify agent tools wrap properly constructed agents

3. **Combined Patterns**
   - Support both delegate and use in same agent definition
   - Verify both patterns work together correctly

4. **Full Pipeline**
   - Test: parse -> analyze -> generate -> load -> create_agent
   - Verify agent hierarchy matches DSL definition
   - Verify tools are resolved correctly

## Success Criteria

- [ ] All integration tests pass
- [ ] Tests cover coordinator pattern with delegate
- [ ] Tests cover hierarchical pattern with use
- [ ] Tests cover combined patterns
- [ ] Tests verify full compilation pipeline
- [ ] Tests use appropriate mocking for external dependencies
- [ ] Code passes linting and type checking

## Acceptance Tests

1. Given a DSL file with `delegate to agent_a, agent_b`, when compiled and loaded, the root agent should have sub_agents containing agent_a and agent_b
2. Given a DSL file with `use agent_c`, when compiled and loaded, the root agent's tools should include an AgentTool wrapping agent_c
3. Given a DSL file with both delegate and use clauses, both should be reflected in the created agent
4. The full pipeline from DSL source string to LlmAgent should work end-to-end
