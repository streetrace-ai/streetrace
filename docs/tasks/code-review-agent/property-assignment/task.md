# Property Assignment Syntax for DSL

## Overview

Extend the StreetRace DSL to support property assignment syntax (`$obj.property = value`) needed by the code review agents to assign values to object properties.

## Design Reference

This task implements Phase 3 from the code review agent implementation plan.

## Key Requirements

1. Grammar must parse `$obj.prop = value` and `$obj.a.b = value`
2. Create a distinct `PropertyAssignment` AST node for clarity
3. Transformer must convert parsed property assignments to AST nodes
4. Code generator must produce nested dict assignment: `ctx.vars['obj']['prop'] = value`

## Acceptance Criteria

1. `$review.findings = $filtered` parses without error
2. `$obj.a.b.c = "value"` parses correctly (nested properties)
3. `PropertyAssignment` node is created with correct target and value
4. Generated Python code uses dictionary subscript notation
5. All existing assignment tests continue to pass (backward compatibility)
6. Integration test successfully modifies an object property
