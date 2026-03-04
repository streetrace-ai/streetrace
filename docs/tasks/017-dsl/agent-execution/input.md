This is triggered by "Tool Passing Inconsistency" tech debt issue documented in `docs/tasks/017-dsl/tech_debt.md`.

We need to ensure proper agent running in general.

The current issue is that the root agents are executed via `src/streetrace/workflow/supervisor.py`, and agents invoked directly from DSL are executed via a shrinked duplicate function.

Option 1: We can create a single module that executes agents (DSL, YAML, or any other). It has to accept all it takes to run an agent, and expose an async generator that runs the agent and passes through all generated events, so we can reuse this module both in the supervisor and in the WorkflowContext. The downside I can see is that execution right from the WorkflowContext seems like a hack more than anything else. What if the flow is the main entry point to DSL? In that case, the control over the main logic falls into WorkflowContext, which is not reasonable.

Option 2: Use `DslStreetRaceAgent.create_agent()` in `WorkflowContext.run_agent()` to make sure the agent is created properly without code duplication. The downsides are similar to Option 1, with an additional point that code duplication between `WorkflowContext.run_agent()` and `Supervisor.handle()` is still there.

Option 3: Pass an instance of the `Supervisor` to `WorkflowContext` somehow. This sounds very smelly.

Option 4: What we really need is a work manager (now assumed by the `Supervisor`) that runs workloads. The workloads can be either DSL flows or direct agents. The work manager interface is a pub/sub that ensures we can run the work manager in a managed / isolated way, not just call from a random place.
