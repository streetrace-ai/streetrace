# Workload Abstraction Test Scenarios

Manual end-to-end test scenarios for validating the Workload Abstraction refactoring.
This document focuses on the unified pipeline for loading workloads from DSL, YAML,
and Python files.

## Feature Scope

The Workload Abstraction introduces these key behaviors to validate:

1. **Unified type hierarchy**: `WorkloadMetadata`, `WorkloadDefinition`, `DefinitionLoader`
2. **Compile-on-load**: DSL compiled during `load()`, not deferred
3. **Required parameters**: No Optional for semantically required fields
4. **Format-specific definitions**: `DslWorkloadDefinition`, `YamlWorkloadDefinition`, `PythonWorkloadDefinition`
5. **WorkloadManager integration**: `discover_definitions()`, `create_workload_from_definition()`
6. **Error handling**: `WorkloadNotFoundError`, early syntax/semantic errors

## Reference Documents

- `docs/tasks/017-dsl/workload-abstraction/task.md`: Task definition, 2026-01-22
- `src/streetrace/workloads/metadata.py`: WorkloadMetadata implementation
- `src/streetrace/workloads/definition.py`: WorkloadDefinition ABC
- `src/streetrace/workloads/loader.py`: DefinitionLoader protocol
- `src/streetrace/workloads/dsl_loader.py`: DslDefinitionLoader
- `src/streetrace/workloads/manager.py`: WorkloadManager extensions

## Test Scenarios

---

### Scenario 1: DSL Compile-on-Load

**Purpose**: Verify DSL files are compiled during `load()`, not deferred.

**Preconditions**:
- Environment set up per [environment-setup.md](environment-setup.md)
- Debug logging enabled: `export STREETRACE_LOG_LEVEL=DEBUG`

**Input File**: `agents/basic_dsl.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting:
    You are a test assistant. Respond briefly.

agent:
    instruction greeting
```

**Test Steps**:

1. Run with debug logging:
   ```bash
   poetry run streetrace agents/basic_dsl.sr "Hello" 2>&1 | tee output.log
   ```

2. Check for compile-on-load evidence:
   ```bash
   grep -E "Loading DSL file|Loaded DSL definition" output.log
   ```

**Expected Output**:
```
DEBUG Loading DSL file: agents/basic_dsl.sr
DEBUG Loaded DSL definition 'basic_dsl' from agents/basic_dsl.sr with workflow class ...
```

**Verification Criteria**:
- [x] "Loading DSL file" appears in logs
- [x] "Loaded DSL definition" appears BEFORE any execution
- [x] Workflow class name is logged
- [x] Agent responds successfully

---

### Scenario 2: DSL Syntax Error Rejection

**Purpose**: Verify invalid DSL files are rejected early during load, not at execution.

**Input File**: `agents/invalid_syntax.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

# Missing colon - intentional syntax error
prompt greeting
    Hello world
```

**Test Steps**:

1. Attempt to run the invalid file:
   ```bash
   poetry run streetrace agents/invalid_syntax.sr "Hello" 2>&1
   ```

**Expected Output**:
```
DslSyntaxError: Expected ':' after prompt name at line 7
```

**Verification Criteria**:
- [x] Error is raised during loading, not execution
- [x] Error message indicates syntax issue
- [x] Line number is provided in error message
- [x] No agent execution occurs

---

### Scenario 3: YAML Definition Loading

**Purpose**: Verify YAML files are parsed and validated during load.

**Input File**: `agents/basic_yaml.yaml`
```yaml
name: yaml_test_agent
description: Test YAML agent
model: anthropic/claude-sonnet
instruction: |
  You are a test assistant. Respond with "YAML agent responding."
```

**Test Steps**:

1. Run with debug logging:
   ```bash
   poetry run streetrace --agent=yaml_test_agent "Hello" 2>&1 | tee output.log
   ```

2. Check for YAML loading:
   ```bash
   grep -E "Loading YAML|Loaded YAML definition" output.log
   ```

**Expected Output**:
```
DEBUG Loading YAML file: agents/basic_yaml.yaml
DEBUG Loaded YAML definition 'yaml_test_agent' from agents/basic_yaml.yaml
```

**Verification Criteria**:
- [x] YAML file is loaded and validated
- [x] Agent name matches the `name` field in YAML
- [x] Agent responds correctly

---

### Scenario 4: Python Definition Loading

**Purpose**: Verify Python agent modules are imported and validated during load.

**Input Directory**: `agents/basic_python/agent.py`

```python
from google.adk.agents import LlmAgent

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


class BasicPythonAgent(StreetRaceAgent):
    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="basic_python_agent",
            description="Basic Python test agent",
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        model = model_factory.get_current_model()
        return LlmAgent(
            name="basic_python_agent",
            model=model.model_id,
            instruction="Respond with 'Python agent responding.'",
        )
```

**Test Steps**:

1. Run with debug logging:
   ```bash
   poetry run streetrace --agent=basic_python_agent "Hello" 2>&1 | tee output.log
   ```

2. Check for Python loading:
   ```bash
   grep -E "Loading Python|Loaded Python definition" output.log
   ```

**Expected Output**:
```
DEBUG Loading Python agent from: agents/basic_python
DEBUG Loaded Python definition 'basic_python_agent' from agents/basic_python with class BasicPythonAgent
```

**Verification Criteria**:
- [x] Python module is imported successfully
- [x] Agent class is found and logged
- [x] Agent card name is used for identification
- [x] Agent responds correctly

---

### Scenario 5: WorkloadMetadata Immutability

**Purpose**: Verify WorkloadMetadata is frozen (immutable).

**Test Steps**:

1. Run Python to verify metadata:
   ```bash
   poetry run python << 'EOF'
   from pathlib import Path
   from streetrace.workloads import DslDefinitionLoader

   loader = DslDefinitionLoader()

   # Create a simple DSL file
   Path("test_meta.sr").write_text("""streetrace v1
   model main = anthropic/claude-sonnet
   prompt p: Hello
   agent:
       instruction p
   """)

   definition = loader.load(Path("test_meta.sr"))
   print(f"Name: {definition.metadata.name}")
   print(f"Format: {definition.metadata.format}")
   print(f"Source: {definition.metadata.source_path}")

   # Try to modify - should fail
   try:
       definition.metadata.name = "changed"
       print("ERROR: Mutation succeeded!")
   except Exception as e:
       print(f"OK: Mutation blocked: {type(e).__name__}")

   Path("test_meta.sr").unlink()
   EOF
   ```

**Expected Output**:
```
Name: test_meta
Format: dsl
Source: test_meta.sr
OK: Mutation blocked: FrozenInstanceError
```

**Verification Criteria**:
- [x] Metadata fields are accessible
- [x] Mutation attempt raises FrozenInstanceError
- [x] Format correctly identified as "dsl"

---

### Scenario 6: WorkloadDefinition Required Fields

**Purpose**: Verify DslWorkloadDefinition has required (not Optional) workflow_class.

**Test Steps**:

1. Run Python to verify required fields:
   ```bash
   poetry run python << 'EOF'
   from pathlib import Path
   from streetrace.workloads import DslDefinitionLoader

   loader = DslDefinitionLoader()

   Path("test_required.sr").write_text("""streetrace v1
   model main = anthropic/claude-sonnet
   prompt p: Hello
   agent:
       instruction p
   """)

   definition = loader.load(Path("test_required.sr"))

   # workflow_class should never be None
   print(f"workflow_class is None: {definition.workflow_class is None}")
   print(f"workflow_class type: {type(definition.workflow_class)}")
   print(f"source_map length: {len(definition.source_map)}")

   Path("test_required.sr").unlink()
   EOF
   ```

**Expected Output**:
```
workflow_class is None: False
workflow_class type: <class 'type'>
source_map length: <some number >= 0>
```

**Verification Criteria**:
- [x] workflow_class is never None after successful load
- [x] source_map is populated (list, may be empty for simple files)

---

### Scenario 7: DefinitionLoader Protocol Compliance

**Purpose**: Verify all loaders implement the DefinitionLoader protocol.

**Test Steps**:

1. Run protocol compliance check:
   ```bash
   poetry run python << 'EOF'
   from streetrace.workloads import (
       DefinitionLoader,
       DslDefinitionLoader,
       YamlDefinitionLoader,
       PythonDefinitionLoader,
   )

   loaders = [
       ("DSL", DslDefinitionLoader()),
       ("YAML", YamlDefinitionLoader()),
       ("Python", PythonDefinitionLoader()),
   ]

   for name, loader in loaders:
       is_protocol = isinstance(loader, DefinitionLoader)
       has_can_load = hasattr(loader, "can_load") and callable(loader.can_load)
       has_load = hasattr(loader, "load") and callable(loader.load)
       has_discover = hasattr(loader, "discover") and callable(loader.discover)

       print(f"{name}Loader:")
       print(f"  Protocol compliant: {is_protocol}")
       print(f"  has can_load: {has_can_load}")
       print(f"  has load: {has_load}")
       print(f"  has discover: {has_discover}")
   EOF
   ```

**Expected Output**:
```
DSLLoader:
  Protocol compliant: True
  has can_load: True
  has load: True
  has discover: True
YAMLLoader:
  Protocol compliant: True
  has can_load: True
  has load: True
  has discover: True
PythonLoader:
  Protocol compliant: True
  has can_load: True
  has load: True
  has discover: True
```

**Verification Criteria**:
- [x] All loaders pass isinstance check for DefinitionLoader
- [x] All loaders have all protocol methods

---

### Scenario 8: WorkloadManager discover_definitions()

**Purpose**: Verify WorkloadManager.discover_definitions() returns WorkloadDefinition objects.

**Test Steps**:

1. Run discovery test:
   ```bash
   poetry run python << 'EOF'
   import os
   import tempfile
   from pathlib import Path
   from unittest.mock import MagicMock

   from streetrace.workloads import WorkloadManager, WorkloadDefinition

   # Create temp directory with test agents
   with tempfile.TemporaryDirectory() as tmpdir:
       agents_dir = Path(tmpdir) / "agents"
       agents_dir.mkdir()

       # Create DSL agent
       (agents_dir / "test_dsl.sr").write_text("""streetrace v1
   model main = anthropic/claude-sonnet
   prompt p: Hello
   agent:
       instruction p
   """)

       # Create YAML agent
       (agents_dir / "test_yaml.yaml").write_text("""
   name: test_yaml
   description: Test
   model: anthropic/claude-sonnet
   instruction: Hello
   """)

       # Create WorkloadManager
       manager = WorkloadManager(
           model_factory=MagicMock(),
           tool_provider=MagicMock(),
           system_context=MagicMock(),
           work_dir=Path(tmpdir),
       )

       # Discover definitions
       definitions = manager.discover_definitions()

       print(f"Found {len(definitions)} definitions")
       for defn in definitions:
           print(f"  {defn.name} ({defn.metadata.format}): {type(defn).__name__}")
           print(f"    Is WorkloadDefinition: {isinstance(defn, WorkloadDefinition)}")
   EOF
   ```

**Expected Output**:
```
Found 2 definitions
  test_dsl (dsl): DslWorkloadDefinition
    Is WorkloadDefinition: True
  test_yaml (yaml): YamlWorkloadDefinition
    Is WorkloadDefinition: True
```

**Verification Criteria**:
- [x] Both DSL and YAML definitions are discovered
- [x] Each definition is a WorkloadDefinition subclass
- [x] Metadata format is correctly set

---

### Scenario 9: WorkloadNotFoundError

**Purpose**: Verify WorkloadNotFoundError is raised for missing workloads.

**Test Steps**:

1. Run error test:
   ```bash
   poetry run python << 'EOF'
   import tempfile
   from pathlib import Path
   from unittest.mock import MagicMock

   from streetrace.workloads import WorkloadManager, WorkloadNotFoundError

   with tempfile.TemporaryDirectory() as tmpdir:
       manager = WorkloadManager(
           model_factory=MagicMock(),
           tool_provider=MagicMock(),
           system_context=MagicMock(),
           work_dir=Path(tmpdir),
           session_service=MagicMock(),
       )

       try:
           workload = manager.create_workload_from_definition("nonexistent_agent")
           print("ERROR: No exception raised!")
       except WorkloadNotFoundError as e:
           print(f"OK: WorkloadNotFoundError raised")
           print(f"  name attribute: {e.name}")
           print(f"  message: {str(e)}")
       except Exception as e:
           print(f"ERROR: Wrong exception type: {type(e).__name__}")
   EOF
   ```

**Expected Output**:
```
OK: WorkloadNotFoundError raised
  name attribute: nonexistent_agent
  message: Workload 'nonexistent_agent' not found
```

**Verification Criteria**:
- [x] WorkloadNotFoundError is raised
- [x] Exception has `name` attribute
- [x] Error message includes workload name

---

### Scenario 10: End-to-End DSL Workload Execution

**Purpose**: Verify complete DSL workload execution through the unified pipeline.

**Input File**: `agents/e2e_test.sr`
```streetrace
streetrace v1

model main = anthropic/claude-sonnet

prompt test_prompt:
    Respond with exactly: "E2E test successful"

agent:
    instruction test_prompt
```

**Test Steps**:

1. Run the agent:
   ```bash
   poetry run streetrace agents/e2e_test.sr "Hello" 2>&1 | tee output.log
   ```

2. Check execution path:
   ```bash
   grep -E "Loading DSL|Loaded DSL|Creating Dsl|DslWorkload" output.log
   ```

**Expected Output**:
Agent response contains "E2E test successful" and logs show:
```
DEBUG Loading DSL file: agents/e2e_test.sr
DEBUG Loaded DSL definition 'e2e_test' from agents/e2e_test.sr ...
DEBUG Created DslWorkload for e2e_test ...
```

**Verification Criteria**:
- [x] DSL file is loaded and compiled
- [x] DslWorkload is created
- [x] Agent executes and responds
- [x] Response contains expected text

---

### Scenario 11: Backward Compatibility - create_workload Context Manager

**Purpose**: Verify existing create_workload() context manager still works.

**Test Steps**:

1. Run the bundled agent:
   ```bash
   poetry run streetrace --agent=Streetrace_Coding_Agent "Say hello briefly" 2>&1 | tee output.log
   ```

2. Verify workload creation:
   ```bash
   grep -E "Loading|Creating.*Workload" output.log
   ```

**Expected Output**:
Agent responds correctly, logs show workload creation.

**Verification Criteria**:
- [x] Bundled agent is discovered
- [x] Workload is created via context manager
- [x] Agent responds successfully
- [x] No errors about missing methods

---

## Validation Checklist

Use this checklist to track test completion:

- [ ] Scenario 1: DSL Compile-on-Load
- [ ] Scenario 2: DSL Syntax Error Rejection
- [ ] Scenario 3: YAML Definition Loading
- [ ] Scenario 4: Python Definition Loading
- [ ] Scenario 5: WorkloadMetadata Immutability
- [ ] Scenario 6: WorkloadDefinition Required Fields
- [ ] Scenario 7: DefinitionLoader Protocol Compliance
- [ ] Scenario 8: WorkloadManager discover_definitions()
- [ ] Scenario 9: WorkloadNotFoundError
- [ ] Scenario 10: End-to-End DSL Workload Execution
- [ ] Scenario 11: Backward Compatibility

## Debugging Tips

### Check Type Creation

Enable debug logging to see workload type selection:

```bash
export STREETRACE_LOG_LEVEL=DEBUG
poetry run streetrace agents/test.sr "Hello" 2>&1 | grep -i workload
```

### Verify Definition Content

Inspect a loaded definition:

```bash
poetry run python << 'EOF'
from pathlib import Path
from streetrace.workloads import DslDefinitionLoader

loader = DslDefinitionLoader()
defn = loader.load(Path("agents/test.sr"))

print(f"Name: {defn.name}")
print(f"Format: {defn.metadata.format}")
print(f"Path: {defn.metadata.source_path}")
print(f"Workflow class: {defn.workflow_class.__name__}")
print(f"Source map entries: {len(defn.source_map)}")
EOF
```

### Check Loader Selection

Verify the correct loader is selected:

```bash
poetry run python << 'EOF'
from pathlib import Path
from streetrace.workloads import DslDefinitionLoader, YamlDefinitionLoader

dsl_loader = DslDefinitionLoader()
yaml_loader = YamlDefinitionLoader()

test_paths = [
    Path("test.sr"),
    Path("test.yaml"),
    Path("test.yml"),
    Path("test.py"),
]

for path in test_paths:
    print(f"{path}: DSL={dsl_loader.can_load(path)}, YAML={yaml_loader.can_load(path)}")
EOF
```

## See Also

- [Environment Setup](environment-setup.md) - Setting up the test environment
- [Testing Guide](testing-guide.md) - General workload testing guide
- `docs/dev/workloads/architecture.md`: Architecture documentation
- `docs/dev/workloads/api-reference.md`: API documentation
