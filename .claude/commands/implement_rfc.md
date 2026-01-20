You are an ORCHESTRATOR and your role is to follow this process. NEVER implement the features on your own.

1. **Discovery Phase**: Scan design docs for file references and build context
2. **Implementation Phase**: Use the Implementer agent to write code with TDD
3. **Documentation Phase**: Use the Documenter agent to create dev and user docs
4. **Quality Phase**: Use the Pre-commit agent to fix all quality issues
5. **Report**: Create a report explaining implementation outcomes.

---

## Step 1: Discover References

First, read all provided design documents and extract file references.

**Documents provided**: $ARGUMENTS

Scan these documents for references to other design docs, RFCs, or specifications.

Read the referenced files to build complete implementation context.

## Step 2: Create Task Definition

Create `./docs/tasks/{feature-id}-task.md` containing:
- Feature name and ID (derived from design doc name)
- Links to all design documents
- Summary of implementation requirements
- Success criteria
- Dependencies on existing code

## Step 3: Create Implementation Plan

Create `./docs/tasks/{feature-id}-todo.md` with ordered implementation steps broken down into
phases. Each phase should include TDD and validation steps. For example:

```markdown
# Implementation Plan: {Feature Name}

## Phase 1: Foundation
- [ ] Understand the scope
- [ ] Create unit tests for main integration points and scenarios
- [ ] Step 1 task description
- [ ] Step 2 task description
- [ ] Run the tests and ensure tests pass
- [ ] Analyze test coverage gaps and create missing tests to ensure high test coverage

## Phase 2: Core Implementation
- [ ] Understand the scope
- [ ] Create unit tests for main integration points and scenarios
- [ ] Step 3 description
- [ ] Run the tests and ensure tests pass
- [ ] Analyze test coverage gaps and create missing tests to ensure high test coverage
...

## Phase 3: Testing & Validation
- [ ] Analyze test coverage gaps and create missing tests to ensure high test coverage
- [ ] Create integration tests and ensure they pass
- [ ] Understand how to test the implemented changes in the app and run the app to test if everything works as expected. Add logs if needed to confirm correctness.
```

## Step 4: Implement with Implementer Agent

Use the Task tool with `subagent_type: implementer` to:

1. Implement core functionality following TDD
2. Ensure all unit tests pass
3. Follow DRY and SOLID principles

Update the todo file with status as implementation progresses.

Run the implementation in phases - for each plan phase, run the implementer agent scoped to that phase.

## Step 5: Validate Implementation

Run manual validation as specified in the design docs:
- Test with example inputs
- Verify expected outputs
- Document any deviations or limitations

You can use model `anthropic/claude-code-4-5` for test runs.

## Step 6: Create Documentation with Documenter Agent

Use the Task tool with `subagent_type: documenter` to create:

**Developer docs** (`./docs/dev/{feature}/`):
- Architecture overview
- API reference
- Extension guide
- Scan all other developer docs in `./docs/dev/` and see if any of the docs are outdated with this implementation. Update those docs to reflect the latest changes.

**User docs** (`./docs/user/{feature}/`):
- Getting started guide
- Examples (derrive from design docs)
- Configuration reference
- Troubleshooting
- Scan all other user docs in `./docs/user/` and see if any of the docs are outdated with this implementation. Update those docs to reflect the latest changes.

**Testing docs** (`./docs/testing/{feature}/`):
- Describe the feature scope and user journeys
- Reference design docs
- Explain how to test these features manually (e.g. by running the app as a user would run it)
- List all example cases, inputs, and outputs you've used in the user docs
- Provide inputs and outputs examples derrived from design docs that add value on top of the examples from user docs
- Think about edge cases and add examples
- Explain how to debug and diagnose issues
- Scan all other testing docs in `./docs/testing/` and see if any of the docs are outdated with this implementation. Update those docs to reflect the latest changes.

## Step 7: User testing

Use the Task tool with `subagent_type: manual-e2e-tester` to test the implemented features providing links to the user (`./docs/user/{feature}/`) and testing (`./docs/testing/{feature}/`) docs created in the previous step:

1. Please test {feature} documented in these docs: {docs}
2. Provide your report in `./docs/testing/{feature}/`.

## Step 8: Quality Checks with Pre-commit Agent

Use the Task tool with `subagent_type: pre-commit` to:

1. Run `make check`
2. Fix ALL issues (linting, types, tests, security)
3. Iterate until all checks pass

## Step 9: Final Summary

After completion, provide:
- Implementation summary with key decisions made
- List of all created/modified files
- Test coverage statistics
- Documentation links
- Any known limitations or follow-up items

---

## Quick Reference: Agent Invocation

```
Task tool with subagent_type: implementer
- For: Writing implementation code with TDD

Task tool with subagent_type: documenter
- For: Creating developer and user documentation

Task tool with subagent_type: pre-commit
- For: Running quality checks and fixing issues
```

---

**Begin implementation now by reading the specified design documents.**
