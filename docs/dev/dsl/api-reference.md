# DSL API Reference

This document provides complete API reference for the Streetrace DSL compiler and runtime
modules. Use this as a lookup guide when integrating with or extending the DSL system.

## Compiler Module

**Module**: `streetrace.dsl.compiler`

The main entry points for DSL compilation and validation.

### compile_dsl

```python
def compile_dsl(
    source: str,
    filename: str,
    *,
    debug_parser: bool = False,
    use_cache: bool = True,
) -> tuple[CodeType, list[SourceMapping]]
```

Compile DSL source to Python bytecode.

Transform DSL source through the complete pipeline: parsing, AST transformation, semantic
analysis, code generation, and compilation.

**Parameters**:
- `source`: The DSL source code string.
- `filename`: Name of the source file (used for error messages and source maps).
- `debug_parser`: Enable parser debug mode for verbose parsing output.
- `use_cache`: Use bytecode caching for repeated compilations (default: True).

**Returns**:
Tuple of (compiled bytecode, source mappings).

**Raises**:
- `DslSyntaxError`: If parsing fails.
- `DslSemanticError`: If semantic analysis fails.
- `SyntaxError`: If generated Python code has syntax errors.

**Example**:

```python
from streetrace.dsl.compiler import compile_dsl

source = """
model main = anthropic/claude-sonnet

prompt greeting:
    Hello, I am a helpful assistant.

agent:
    instruction greeting
"""

bytecode, source_map = compile_dsl(source, "my_agent.sr")
```

**Location**: `src/streetrace/dsl/compiler.py:58`

### validate_dsl

```python
def validate_dsl(
    source: str,
    filename: str,
    *,
    debug_parser: bool = False,
) -> list[Diagnostic]
```

Validate DSL source without compilation.

Perform parsing and semantic analysis to produce diagnostics without generating or
compiling code. Used by the `check` command.

**Parameters**:
- `source`: The DSL source code string.
- `filename`: Name of the source file.
- `debug_parser`: Enable parser debug mode.

**Returns**:
List of `Diagnostic` objects (errors and warnings).

**Example**:

```python
from streetrace.dsl.compiler import validate_dsl

diagnostics = validate_dsl(source, "my_agent.sr")
for d in diagnostics:
    print(f"{d.severity}: {d.message}")
```

**Location**: `src/streetrace/dsl/compiler.py:149`

### get_file_stats

```python
def get_file_stats(source: str, filename: str) -> dict[str, int]
```

Get statistics about a DSL file.

**Parameters**:
- `source`: The DSL source code string.
- `filename`: Name of the source file (used for future error context).

**Returns**:
Dictionary with counts: `{"models": N, "agents": N, "flows": N, "handlers": N}`.

**Location**: `src/streetrace/dsl/compiler.py:258`

### Exception Classes

#### DslError

```python
class DslError(Exception):
    def __init__(self, message: str, *, filename: str | None = None) -> None
```

Base exception for DSL compiler errors.

**Attributes**:
- `filename`: Optional source filename.

**Location**: `src/streetrace/dsl/compiler.py:364`

#### DslSyntaxError

```python
class DslSyntaxError(DslError):
    def __init__(
        self,
        message: str,
        *,
        filename: str | None = None,
        parse_error: Exception | None = None,
    ) -> None
```

Exception for DSL parsing/syntax errors.

**Attributes**:
- `filename`: Source filename.
- `parse_error`: Original Lark parse error.

**Location**: `src/streetrace/dsl/compiler.py:379`

#### DslSemanticError

```python
class DslSemanticError(DslError):
    def __init__(
        self,
        message: str,
        *,
        filename: str | None = None,
        errors: list[SemanticError] | None = None,
    ) -> None
```

Exception for DSL semantic analysis errors.

**Attributes**:
- `filename`: Source filename.
- `errors`: List of `SemanticError` objects.

**Location**: `src/streetrace/dsl/compiler.py:401`

## Runtime Module

**Module**: `streetrace.dsl.runtime`

Runtime classes for executing generated DSL workflows.

### DslAgentWorkflow

```python
class DslAgentWorkflow:
    _models: ClassVar[dict[str, str]] = {}
    _prompts: ClassVar[dict[str, object]] = {}
    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    _agents: ClassVar[dict[str, dict[str, object]]] = {}
```

Base class for generated DSL workflows.

Generated workflows extend this class and override the class attributes and event handler
methods. The code generator populates the class variables with definitions from the DSL.

**Class Attributes**:
- `_models`: Model definitions mapping name to model identifier.
- `_prompts`: Prompt definitions mapping name to template (string or lambda).
- `_tools`: Tool definitions mapping name to configuration dict.
- `_agents`: Agent definitions mapping name to configuration dict.

**Location**: `src/streetrace/dsl/runtime/workflow.py:14`

#### create_context

```python
def create_context(self) -> WorkflowContext
```

Create a new workflow context for execution.

Initializes the context with models, prompts, and agents from the workflow's class
attributes.

**Returns**:
A fresh `WorkflowContext` instance.

#### Event Handler Methods

All event handlers are async methods that receive a `WorkflowContext`:

```python
async def on_start(self, ctx: WorkflowContext) -> None
async def on_input(self, ctx: WorkflowContext) -> None
async def on_output(self, ctx: WorkflowContext) -> None
async def on_tool_call(self, ctx: WorkflowContext) -> None
async def on_tool_result(self, ctx: WorkflowContext) -> None
async def after_start(self, ctx: WorkflowContext) -> None
async def after_input(self, ctx: WorkflowContext) -> None
async def after_output(self, ctx: WorkflowContext) -> None
async def after_tool_call(self, ctx: WorkflowContext) -> None
async def after_tool_result(self, ctx: WorkflowContext) -> None
```

Override these methods to implement custom event handling logic.

### WorkflowContext

```python
class WorkflowContext:
    vars: dict[str, object]
    message: str
    guardrails: GuardrailProvider
```

Execution context for DSL workflows.

Provides access to variables, agents, LLM calls, and other runtime services needed by
generated workflow code.

**Attributes**:
- `vars`: Variable storage for workflow execution.
- `message`: Current message being processed.
- `guardrails`: GuardrailProvider for security operations.

**Location**: `src/streetrace/dsl/runtime/context.py:127`

#### set_models

```python
def set_models(self, models: dict[str, str]) -> None
```

Set the available models.

**Parameters**:
- `models`: Dictionary mapping model name to model identifier.

#### set_prompts

```python
def set_prompts(self, prompts: dict[str, object]) -> None
```

Set the available prompts.

**Parameters**:
- `prompts`: Dictionary mapping prompt name to template.

#### set_agents

```python
def set_agents(self, agents: dict[str, dict[str, object]]) -> None
```

Set the available agents.

**Parameters**:
- `agents`: Dictionary mapping agent name to configuration.

#### run_agent

```python
async def run_agent(self, agent_name: str, *args: object) -> object
```

Run a named agent with arguments.

Create an ADK LlmAgent from the agent configuration and execute it with the provided
arguments as the user prompt.

**Parameters**:
- `agent_name`: Name of the agent to run.
- `*args`: Arguments to pass (joined as prompt text).

**Returns**:
Result from the agent execution, or None if agent not found.

**Example**:

```python
result = await ctx.run_agent("summarizer", analysis_text)
```

**Location**: `src/streetrace/dsl/runtime/context.py:222`

#### call_llm

```python
async def call_llm(
    self,
    prompt_name: str,
    *args: object,
    model: str | None = None,
) -> object
```

Call an LLM with a named prompt.

Look up the prompt by name, evaluate it with the context, and call the LLM.

**Parameters**:
- `prompt_name`: Name of the prompt to use.
- `*args`: Arguments for prompt interpolation.
- `model`: Optional model override.

**Returns**:
LLM response content, or None on error.

**Location**: `src/streetrace/dsl/runtime/context.py:340`

#### log / warn / notify

```python
def log(self, message: str) -> None
def warn(self, message: str) -> None
def notify(self, message: str) -> None
```

Logging and notification methods for workflow code.

#### escalate_to_human

```python
async def escalate_to_human(self, message: str | None = None) -> None
```

Escalate to human operator.

Log the escalation, call any registered callback, and dispatch a UI event if configured.

**Parameters**:
- `message`: Optional message for the human.

**Location**: `src/streetrace/dsl/runtime/context.py:666`

### GuardrailProvider

```python
class GuardrailProvider:
    async def mask(self, guardrail: str, message: str) -> str
    async def check(self, guardrail: str, message: str) -> bool
```

Provider for guardrail operations.

**Location**: `src/streetrace/dsl/runtime/context.py:58`

#### mask

```python
async def mask(self, guardrail: str, message: str) -> str
```

Mask sensitive content in a message.

Apply regex-based masking for common PII types including emails, phone numbers, SSNs, and
credit card numbers.

**Parameters**:
- `guardrail`: Name of the guardrail (currently only "pii" is supported).
- `message`: Message to mask.

**Returns**:
Message with sensitive content replaced by placeholders like `[EMAIL]`, `[PHONE]`,
`[SSN]`, `[CREDIT_CARD]`.

#### check

```python
async def check(self, guardrail: str, message: str) -> bool
```

Check if a message triggers a guardrail.

Use pattern-based detection to identify common jailbreak attempts.

**Parameters**:
- `guardrail`: Name of the guardrail (currently only "jailbreak" is supported).
- `message`: Message to check.

**Returns**:
True if the guardrail is triggered.

## Loader Module

**Module**: `streetrace.dsl.loader`

Simple loader for workflow classes.

### DslAgentLoader (dsl/)

```python
class DslAgentLoader:
    def __init__(self, cache: BytecodeCache | None = None) -> None
```

Loader for `.sr` DSL agent files.

Load and discover Streetrace DSL files, compiling them to executable workflow classes.

**Parameters**:
- `cache`: Optional bytecode cache. Uses global cache if not provided.

**Location**: `src/streetrace/dsl/loader.py:37`

#### can_load

```python
def can_load(self, path: Path) -> bool
```

Check if this loader can handle the given path.

**Returns**:
True if path has `.sr` extension.

#### load

```python
def load(self, path: Path) -> type[DslAgentWorkflow]
```

Load a DSL file and return a workflow class.

Compile the DSL file to Python bytecode and run it to obtain the workflow class.

**Parameters**:
- `path`: Path to the `.sr` file.

**Returns**:
Generated workflow class.

**Raises**:
- `FileNotFoundError`: If the file does not exist.
- `DslSyntaxError`: If parsing fails.
- `DslSemanticError`: If semantic analysis fails.
- `ValueError`: If no workflow class is found.

**Example**:

```python
from pathlib import Path
from streetrace.dsl.loader import DslAgentLoader

loader = DslAgentLoader()
workflow_class = loader.load(Path("my_agent.sr"))
workflow = workflow_class()
ctx = workflow.create_context()
```

#### discover

```python
def discover(self, directory: Path) -> list[Path]
```

Discover all `.sr` files in a directory recursively.

**Parameters**:
- `directory`: Directory to search.

**Returns**:
List of paths to discovered `.sr` files.

## Agent Loader Module

**Module**: `streetrace.agents.dsl_agent_loader`

Full agent loader implementing the AgentLoader interface.

### DslAgentLoader (agents/)

```python
class DslAgentLoader(AgentLoader):
    def __init__(self) -> None
```

Agent loader for `.sr` DSL files.

Discover and load Streetrace DSL files, compiling them to executable workflow classes
that can be used as agents through the AgentManager.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:58`

#### discover_in_paths

```python
def discover_in_paths(self, paths: list[Path]) -> list[AgentInfo]
```

Discover `.sr` agents in specific paths.

**Parameters**:
- `paths`: Specific paths to search in.

**Returns**:
List of `DslAgentInfo` instances.

#### load_from_path

```python
def load_from_path(self, path: Path) -> StreetRaceAgent
```

Load agent from explicit file path.

**Parameters**:
- `path`: Path to `.sr` file.

**Returns**:
`DslStreetRaceAgent` wrapping the compiled workflow.

**Raises**:
- `ValueError`: If cannot load from this path.

#### load_agent

```python
def load_agent(self, agent_info: AgentInfo) -> StreetRaceAgent
```

Load agent from AgentInfo (from discovery).

**Parameters**:
- `agent_info`: Previously discovered agent info.

**Returns**:
`DslStreetRaceAgent` wrapping the compiled workflow.

### DslAgentInfo

```python
class DslAgentInfo(AgentInfo):
    def __init__(
        self,
        name: str,
        description: str,
        file_path: Path,
        workflow_class: type[DslAgentWorkflow] | None = None,
    ) -> None
```

Agent information container for DSL agents.

**Attributes**:
- `name`: Agent name (from filename).
- `description`: Agent description (from first comment).
- `file_path`: Path to the `.sr` file.
- `workflow_class`: Compiled workflow class (optional).
- `kind`: Always returns "dsl".

**Location**: `src/streetrace/agents/dsl_agent_loader.py:30`

### DslStreetRaceAgent

```python
class DslStreetRaceAgent(StreetRaceAgent):
    def __init__(
        self,
        workflow_class: type[DslAgentWorkflow],
        source_file: Path,
        source_map: list[SourceMapping],
    ) -> None
```

StreetRaceAgent wrapper for compiled DSL workflows.

Wrap a compiled DSL workflow class to implement the StreetRaceAgent interface required
by the AgentManager.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:290`

#### create_agent

```python
async def create_agent(
    self,
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> BaseAgent
```

Create the ADK agent from the DSL workflow.

Create the root `LlmAgent` with support for agentic patterns:
- Coordinator/dispatcher pattern via `sub_agents` (delegate keyword)
- Hierarchical pattern via `AgentTool` (use keyword)

**Parameters**:
- `model_factory`: Factory for creating LLM models.
- `tool_provider`: Provider for tools.
- `system_context`: System context.

**Returns**:
The root ADK agent (LlmAgent).

**Location**: `src/streetrace/agents/dsl_agent_loader.py:341`

#### _create_agent_from_def

```python
async def _create_agent_from_def(
    self,
    name: str,
    agent_def: dict[str, object],
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> BaseAgent
```

Create an `LlmAgent` from an agent definition dict.

Used for creating both the root agent and sub-agents. Handles instruction, model, tools
resolution and recursively resolves nested agentic patterns.

**Parameters**:
- `name`: Name for the agent.
- `agent_def`: Agent definition dict with tools, instruction, sub_agents, agent_tools.
- `model_factory`: Factory for creating LLM models.
- `tool_provider`: Provider for tools.
- `system_context`: System context.

**Returns**:
The created ADK `LlmAgent` instance.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:644`

#### _resolve_sub_agents

```python
async def _resolve_sub_agents(
    self,
    agent_def: dict[str, object],
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> list[BaseAgent]
```

Resolve sub_agents for the coordinator/dispatcher pattern.

Create `LlmAgent` instances for each agent listed in `sub_agents`. This enables the
`delegate` keyword functionality.

**Parameters**:
- `agent_def`: Agent definition dict with optional `sub_agents` list.
- `model_factory`: Factory for creating LLM models.
- `tool_provider`: Provider for tools.
- `system_context`: System context.

**Returns**:
List of created sub-agent instances.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:699`

#### _resolve_agent_tools

```python
async def _resolve_agent_tools(
    self,
    agent_def: dict[str, object],
    model_factory: ModelFactory,
    tool_provider: ToolProvider,
    system_context: SystemContext,
) -> list[AdkTool]
```

Resolve agent_tools for the hierarchical pattern.

Create `AgentTool` wrappers for each agent listed in `agent_tools`. This enables the
`use` keyword functionality.

**Parameters**:
- `agent_def`: Agent definition dict with optional `agent_tools` list.
- `model_factory`: Factory for creating LLM models.
- `tool_provider`: Provider for tools.
- `system_context`: System context.

**Returns**:
List of `AgentTool` instances wrapping the child agents.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:751`

#### _close_agent_recursive

```python
async def _close_agent_recursive(self, agent: BaseAgent) -> None
```

Recursively close agent, its sub-agents, and tools.

Traverse the agent hierarchy depth-first, closing sub-agents before parent agents.
For `AgentTool` instances, close the wrapped agent first.

**Parameters**:
- `agent`: The agent to close.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:815`

#### close

```python
async def close(self, agent_instance: BaseAgent) -> None
```

Clean up resources including sub-agents and agent tools.

**Parameters**:
- `agent_instance`: The root agent instance to close.

**Location**: `src/streetrace/agents/dsl_agent_loader.py:805`

#### get_agent_card

```python
def get_agent_card(self) -> StreetRaceAgentCard
```

Provide an A2A AgentCard for the DSL agent.

## CLI Module

**Module**: `streetrace.dsl.cli`

Command-line interface functions for DSL operations.

### check_file

```python
def check_file(
    file_path: Path,
    *,
    verbose: bool = False,
    json_output: bool = False,
    strict: bool = False,
) -> int
```

Validate a single DSL file.

**Parameters**:
- `file_path`: Path to the DSL file.
- `verbose`: Enable verbose output.
- `json_output`: Output results as JSON.
- `strict`: Treat warnings as errors.

**Returns**:
Exit code (0=success, 1=errors, 2=file error).

**Location**: `src/streetrace/dsl/cli.py:107`

### check_directory

```python
def check_directory(
    dir_path: Path,
    *,
    verbose: bool = False,
    json_output: bool = False,
    strict: bool = False,
) -> int
```

Validate all DSL files in a directory recursively.

**Parameters**:
- `dir_path`: Path to the directory.
- `verbose`: Enable verbose output.
- `json_output`: Output results as JSON.
- `strict`: Treat warnings as errors.

**Returns**:
Exit code (0=success, 1=errors, 2=file error).

**Location**: `src/streetrace/dsl/cli.py:170`

### dump_python

```python
def dump_python(
    file_path: Path,
    *,
    include_comments: bool = True,
    output_file: Path | None = None,
) -> int
```

Generate Python code from DSL file and output it.

**Parameters**:
- `file_path`: Path to the DSL file.
- `include_comments`: Include source comments in output.
- `output_file`: Optional output file path.

**Returns**:
Exit code (0=success, 2=error).

**Location**: `src/streetrace/dsl/cli.py:223`

### Exit Codes

| Code | Constant | Description |
|------|----------|-------------|
| 0 | `EXIT_SUCCESS` | Validation passed |
| 1 | `EXIT_VALIDATION_ERRORS` | Validation errors found |
| 2 | `EXIT_FILE_ERROR` | File not found or cannot be read |

## Semantic Analysis Module

**Module**: `streetrace.dsl.semantic.analyzer`

### SemanticAnalyzer

```python
class SemanticAnalyzer:
    def __init__(self) -> None
    def analyze(self, ast: DslFile) -> AnalysisResult
```

Semantic analyzer for DSL AST.

Validate the AST for semantic correctness through symbol collection and reference
validation passes.

**Location**: `src/streetrace/dsl/semantic/analyzer.py:82`

### AnalysisResult

```python
@dataclass
class AnalysisResult:
    is_valid: bool
    errors: list[SemanticError]
    warnings: list[SemanticError]
    symbols: SymbolTable
```

Result of semantic analysis.

**Attributes**:
- `is_valid`: True if no errors were found.
- `errors`: List of semantic errors.
- `warnings`: List of semantic warnings.
- `symbols`: Collected symbol table.

## Code Generation Module

**Module**: `streetrace.dsl.codegen.generator`

### CodeGenerator

```python
class CodeGenerator:
    def __init__(self) -> None
    def generate(
        self,
        ast: DslFile,
        source_file: str,
    ) -> tuple[str, list[SourceMapping]]
```

Code generator for DSL AST.

Transform validated AST into Python source code with source mappings.

**Parameters**:
- `ast`: The validated DslFile AST.
- `source_file`: Path to the source file (for comments).

**Returns**:
Tuple of (Python source code, source mappings).

**Location**: `src/streetrace/dsl/codegen/generator.py:15`

## Diagnostics Module

**Module**: `streetrace.dsl.errors.diagnostics`

### Diagnostic

```python
@dataclass
class Diagnostic:
    severity: Severity
    message: str
    file: str
    line: int
    column: int
    code: ErrorCode | None = None
    end_line: int | None = None
    end_column: int | None = None
    help_text: str | None = None
```

Diagnostic message for compiler errors and warnings.

**Class Methods**:
- `error(...)`: Create an error diagnostic.
- `warning(...)`: Create a warning diagnostic.

### Severity

```python
class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
```

Diagnostic severity levels.

## Source Map Module

**Module**: `streetrace.dsl.sourcemap.registry`

### SourceMapping

```python
@dataclass
class SourceMapping:
    generated_line: int
    source_line: int
    source_column: int = 0
```

Mapping from generated Python line to source DSL position.

### SourceMapRegistry

```python
class SourceMapRegistry:
    def add_mapping(
        self,
        generated_file: str,
        mapping: SourceMapping,
    ) -> None

    def get_source_location(
        self,
        generated_file: str,
        generated_line: int,
    ) -> tuple[int, int] | None
```

Registry for source mappings across multiple compiled files.

## See Also

- [Architecture Overview](architecture.md) - Compiler pipeline overview
- [Extension Guide](extending.md) - Adding new features
- [CLI Reference](../../user/dsl/cli-reference.md) - Command-line tools
