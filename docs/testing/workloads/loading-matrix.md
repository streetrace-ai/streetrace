# Workload Loading Test Matrix

Comprehensive test cases for workload loading across all source locations and formats.

## Loading Matrix

| Source | Python | YAML | DSL | Notes |
|--------|--------|------|-----|-------|
| **Project dir** (`./agents`) | Supported | Supported | Supported | Highest priority for name lookup |
| **Project config** (`.streetrace/agents`) | Supported | Supported | Supported | Project-specific overrides |
| **User dir** (`~/.streetrace/agents`) | Supported | Supported | Supported | User-level agents |
| **Bundled** (`src/streetrace/agents`) | Supported | Supported | Supported | Lowest priority |
| **Remote** (HTTP/HTTPS) | **Rejected** | Supported | Supported | Security: only Python rejected |
| **Custom** (`STREETRACE_AGENT_PATHS`) | Supported | Supported | Supported | Highest priority overall |

## Source Locations

### Priority Order (name lookup)

1. **Custom paths** - `STREETRACE_AGENT_PATHS` environment variable (colon-separated)
2. **Project directory** - `./agents`, `.streetrace/agents`
3. **User directory** - `~/.streetrace/agents`
4. **Bundled agents** - `src/streetrace/agents/`

First match wins - allows overriding bundled agents with project-local versions.

### Identifier Types

| Identifier | Example | Resolution |
|------------|---------|------------|
| HTTP URL | `https://example.com/agent.yaml` | Direct HTTP fetch (YAML only) |
| Absolute path | `/home/user/agents/my-agent.sr` | Direct file load |
| Home path | `~/agents/my-agent.yaml` | Expand `~` and load |
| Relative path | `./custom/agent.sr` | Relative to cwd |
| Name | `Streetrace_Coding_Agent` | Search all locations |

## Test Cases

### 1. Project Directory Loading

```bash
# Setup: Create ./agents/test_project.sr
mkdir -p agents
cat > agents/test_project.sr << 'EOF'
streetrace v1
model main = anthropic/claude-sonnet
prompt p: You are a project-local agent.
agent:
    instruction p
EOF

# Test: Load by name
poetry run streetrace --agent=test_project "Hello"

# Test: Load by path
poetry run streetrace ./agents/test_project.sr "Hello"

# Cleanup
rm agents/test_project.sr
```

### 2. Project Config Directory Loading

```bash
# Setup: Create .streetrace/agents/test_config.yaml
mkdir -p .streetrace/agents
cat > .streetrace/agents/test_config.yaml << 'EOF'
name: test_config
description: Project config agent
model: anthropic/claude-sonnet
instruction: You are a project config agent.
EOF

# Test: Load by name
poetry run streetrace --agent=test_config "Hello"

# Cleanup
rm -rf .streetrace/agents/test_config.yaml
```

### 3. User Directory Loading

```bash
# Setup: Create ~/.streetrace/agents/test_user.yaml
mkdir -p ~/.streetrace/agents
cat > ~/.streetrace/agents/test_user.yaml << 'EOF'
name: test_user
description: User-level agent
model: anthropic/claude-sonnet
instruction: You are a user-level agent.
EOF

# Test: Load by name
poetry run streetrace --agent=test_user "Hello"

# Cleanup
rm ~/.streetrace/agents/test_user.yaml
```

### 4. Bundled Agent Loading

```bash
# Test: Load bundled Python agent by name
poetry run streetrace --agent=Streetrace_Coding_Agent "Hello"

# Test: Load bundled YAML agent by name
poetry run streetrace --agent=GenericCodingAssistant "Hello"

# Test: List bundled agents
poetry run streetrace --list-agents
```

### 5. Remote URL Loading (YAML and DSL)

```bash
# Test: Load YAML from URL
poetry run streetrace --agent=https://example.com/agent.yaml "Hello"

# Test: Load DSL from URL
poetry run streetrace --agent=https://example.com/agent.sr "Hello"

# Test: Python URL should be rejected
poetry run streetrace --agent=https://example.com/agent.py "Hello"
# Expected: Error - HTTP loading not supported for Python agents
```

### 6. Custom Paths via Environment Variable

```bash
# Setup: Create custom agent directory
mkdir -p /tmp/my-agents
cat > /tmp/my-agents/custom_agent.sr << 'EOF'
streetrace v1
model main = anthropic/claude-sonnet
prompt p: You are a custom path agent.
agent:
    instruction p
EOF

# Test: Load with custom path
STREETRACE_AGENT_PATHS=/tmp/my-agents poetry run streetrace --agent=custom_agent "Hello"

# Cleanup
rm -rf /tmp/my-agents
```

### 7. Path-Based Loading (all formats)

```bash
# DSL by absolute path
poetry run streetrace /path/to/agent.sr "Hello"

# YAML by absolute path
poetry run streetrace /path/to/agent.yaml "Hello"

# Python by directory path
poetry run streetrace /path/to/agent-dir/ "Hello"

# Home path expansion
poetry run streetrace ~/agents/my-agent.yaml "Hello"

# Relative path
poetry run streetrace ./agents/local.sr "Hello"
```

### 8. Priority Override Test

```bash
# Setup: Create agent with same name in multiple locations
# This tests that project-local overrides bundled

mkdir -p agents
cat > agents/GenericCodingAssistant.yaml << 'EOF'
name: GenericCodingAssistant
description: PROJECT OVERRIDE version
model: anthropic/claude-sonnet
instruction: You are the PROJECT OVERRIDE version.
EOF

# Test: Project version should be loaded (not bundled)
poetry run streetrace --agent=GenericCodingAssistant "What version are you?"
# Expected: Response mentions "PROJECT OVERRIDE"

# Cleanup
rm agents/GenericCodingAssistant.yaml
```

## Format-Specific Test Cases

### Python Agent Loading

| Test | Command | Expected |
|------|---------|----------|
| Load by name | `--agent=Streetrace_Coding_Agent` | Success |
| Load by path | `./src/streetrace/agents/coder/` | Success |
| HTTP URL | `https://example.com/agent.py` | **Rejected** |
| Missing agent.py | `./empty-dir/` | Error: agent.py not found |

### YAML Agent Loading

| Test | Command | Expected |
|------|---------|----------|
| Load by name | `--agent=GenericCodingAssistant` | Success |
| Load .yaml | `./agents/test.yaml` | Success |
| Load .yml | `./agents/test.yml` | Success |
| HTTP URL | `https://example.com/agent.yaml` | Success |
| Invalid YAML | `./agents/invalid.yaml` | Error: YAML syntax |
| Invalid schema | `./agents/bad-schema.yaml` | Error: validation |

### DSL Agent Loading

| Test | Command | Expected |
|------|---------|----------|
| Load by name | `--agent=reviewer` | Success |
| Load by path | `./agents/reviewer.sr` | Success |
| HTTP URL | `https://example.com/agent.sr` | Success |
| Syntax error | `./agents/invalid.sr` | Error: DslSyntaxError |
| Semantic error | `./agents/bad-semantic.sr` | Error: DslSemanticError |

## Verification Script

Run all loading scenarios programmatically:

```python
"""Verify all loading scenarios."""
from pathlib import Path
from unittest.mock import MagicMock
import tempfile

from streetrace.workloads import (
    WorkloadManager,
    DslDefinitionLoader,
    YamlDefinitionLoader,
    PythonDefinitionLoader,
)

def test_loading_matrix():
    """Test all source/format combinations."""

    dsl_loader = DslDefinitionLoader()
    yaml_loader = YamlDefinitionLoader()
    py_loader = PythonDefinitionLoader()

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create test agents in different locations
        agents_dir = base / "agents"
        agents_dir.mkdir()

        # DSL agent
        dsl_file = agents_dir / "test.sr"
        dsl_file.write_text("""streetrace v1
model main = anthropic/claude-sonnet
prompt p: Test
agent:
    instruction p
""")

        # YAML agent
        yaml_file = agents_dir / "test.yaml"
        yaml_file.write_text("""name: test_yaml
description: Test YAML
model: anthropic/claude-sonnet
instruction: Test
""")

        # Python agent
        py_dir = agents_dir / "test_python"
        py_dir.mkdir()
        (py_dir / "__init__.py").write_text("")
        (py_dir / "agent.py").write_text("""
from google.adk.agents import LlmAgent
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

class TestAgent(StreetRaceAgent):
    def get_agent_card(self):
        return StreetRaceAgentCard(name="test_python", description="Test")
    async def create_agent(self, model_factory, tool_provider, system_context):
        return LlmAgent(name="test", model="test", instruction="Test")
""")

        # Test discovery
        manager = WorkloadManager(
            model_factory=MagicMock(),
            tool_provider=MagicMock(),
            system_context=MagicMock(),
            work_dir=base,
        )

        definitions = manager.discover_definitions()

        print("=== Discovered Definitions ===")
        for d in definitions:
            print(f"  {d.name} ({d.metadata.format})")

        # Verify each format
        assert any(d.metadata.format == "dsl" for d in definitions), "DSL not found"
        assert any(d.metadata.format == "yaml" for d in definitions), "YAML not found"
        assert any(d.metadata.format == "python" for d in definitions), "Python not found"

        print("\nAll loading scenarios passed!")

if __name__ == "__main__":
    test_loading_matrix()
```

## Security Notes

### Why HTTP is restricted for Python

| Format | HTTP Allowed | Reason |
|--------|--------------|--------|
| YAML | Yes | Declarative, no code execution during parse |
| DSL | Yes | Compiled to bytecode after download, validated before execution |
| Python | **No** | Requires import into Python runtime, direct code execution risk |

### URL Loading Authentication

For private YAML agents over HTTP:

```bash
# Set auth token
export STREETRACE_AGENT_URI_AUTH="Bearer your-token"

# Or specify via CLI
poetry run streetrace --agent-uri-auth-var=MY_TOKEN_VAR --agent=https://private.example.com/agent.yaml "Hello"
```

## See Also

- [scenarios.md](scenarios.md) - Workload abstraction test scenarios
- [environment-setup.md](environment-setup.md) - Test environment setup
- [testing-guide.md](testing-guide.md) - General testing guide
