# Grammar Development Guide

This guide covers how to modify and extend the Streetrace DSL grammar. The grammar is
defined using Lark's EBNF-like syntax with a custom indenter for Python-style significant
whitespace.

## Overview

The grammar defines the syntax for `.sr` files. Changes to the grammar affect what users
can write and how it parses. Grammar modifications typically require corresponding changes
to the AST transformer and potentially the semantic analyzer and code generator.

## Grammar Location

The grammar is defined in a single file:

```
src/streetrace/dsl/grammar/streetrace.lark
```

## Lark Basics

### Rule Syntax

Rules are defined using `rule_name: pattern`:

```lark
// Terminal (token) - uppercase
NAME: /[a-zA-Z_][a-zA-Z0-9_]*/

// Non-terminal (rule) - lowercase
identifier: NAME
           | contextual_keyword
```

### Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `|` | Alternation | `"true" | "false"` |
| `?` | Optional (0 or 1) | `version_decl?` |
| `*` | Zero or more | `statement*` |
| `+` | One or more | `schema_field+` |
| `( )` | Grouping | `("," expression)*` |
| `~n` | Exactly n times | `HEX~4` |
| `~n..m` | n to m times | `DIGIT~1..3` |

### Priorities

Higher priority rules are tried first. Use `!` to increase terminal priority:

```lark
NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
KEYWORD.2: "model" | "agent" | "flow"  // Higher priority
```

For non-terminals, use numbered suffixes:

```lark
expression.1: or_expr  // Lower priority
expression.2: atom     // Higher priority (tried first)
```

### Inline Rules

Rules prefixed with `_` are inlined (their children are hoisted to the parent):

```lark
_separator: "," | ";"  // Won't appear in parse tree
```

## Indentation Handling

Streetrace uses Python-style significant whitespace. The custom indenter in
`src/streetrace/dsl/grammar/indenter.py` converts indentation to `_INDENT` and `_DEDENT`
tokens.

### Indenter Configuration

```python
class StreetRaceIndenter(Indenter):
    NL_type = "_NL"
    OPEN_PAREN_types: list[str] = []
    CLOSE_PAREN_types: list[str] = []
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4
```

**Location**: `src/streetrace/dsl/grammar/indenter.py:15`

### Using Indentation in Rules

Use `_INDENT` and `_DEDENT` to define indented blocks:

```lark
agent_body: _INDENT agent_property+ _DEDENT

flow_def: "flow" flow_name flow_params? ":" _NL flow_body

flow_body: _INDENT flow_statement+ _DEDENT
```

## Common Patterns

### Defining Keywords

Keywords should be defined as terminals with high priority:

```lark
// Keywords as terminals
MODEL: "model"
AGENT: "agent"
FLOW: "flow"

// Use in rules
model_short: MODEL NAME PROVIDER_MODEL
```

### Contextual Keywords

Some words are keywords in specific contexts but valid identifiers elsewhere:

```lark
contextual_keyword: "model" | "agent" | "flow" | "prompt"
                  | "tool" | "schema" | "policy"

identifier: NAME | contextual_keyword
```

### String Literals

Support multiple string formats:

```lark
STRING: /"[^"]*"/ | /'[^']*'/
TRIPLE_QUOTED_STRING: /"{3}[\s\S]*?"{3}/ | /'{3}[\s\S]*?'{3}/
```

### Block Structures

Define structures with indented bodies:

```lark
if_block: "if" expression ":" _NL _INDENT flow_statement+ _DEDENT

for_loop: "for" variable "in" expression ":" _NL _INDENT flow_statement+ _DEDENT
```

### Property Lists

For constructs with multiple optional properties:

```lark
agent_body: _INDENT agent_property+ _DEDENT

agent_property: agent_tools
              | agent_instruction
              | agent_retry
              | agent_timeout
              | agent_description

agent_tools: "tools" ":" name_list
agent_instruction: "instruction" ":" STRING
```

## Adding New Syntax

### Step 1: Define the Grammar Rule

Add the rule to `streetrace.lark`:

```lark
// Example: Adding a "cache" construct
cache_def: "cache" NAME ":" _NL cache_body
cache_body: _INDENT cache_property+ _DEDENT
cache_property: cache_ttl | cache_size
cache_ttl: "ttl" ":" INT time_unit
cache_size: "size" ":" INT
```

### Step 2: Add AST Node

Create a corresponding node in `src/streetrace/dsl/ast/nodes.py`:

```python
@dataclass
class CacheDef:
    """Cache definition node."""

    name: str
    ttl: int | None = None
    ttl_unit: str = "seconds"
    size: int | None = None
    meta: SourcePosition | None = None
```

### Step 3: Update the Transformer

Add transformation methods in `src/streetrace/dsl/ast/transformer.py`:

```python
def cache_def(self, items: TransformerItems) -> CacheDef:
    """Transform cache_def rule."""
    filtered = _filter_children(items)
    name = None
    properties = {}

    for item in filtered:
        if isinstance(item, dict):
            properties.update(item)
        elif isinstance(item, (str, Token)) and name is None:
            name = _get_token_value(item) if isinstance(item, Token) else item

    return CacheDef(
        name=name or "",
        ttl=properties.get("ttl"),
        ttl_unit=properties.get("ttl_unit", "seconds"),
        size=properties.get("size"),
    )

def cache_ttl(self, items: TransformerItems) -> dict:
    """Transform cache_ttl rule."""
    return {"ttl": items[0], "ttl_unit": items[1]}

def cache_size(self, items: TransformerItems) -> dict:
    """Transform cache_size rule."""
    return {"size": items[0]}
```

### Step 4: Add Semantic Validation

Update `src/streetrace/dsl/semantic/analyzer.py` if validation is needed:

```python
def _collect_cache(self, cache: CacheDef) -> None:
    """Collect a cache definition."""
    if cache.name in self._symbols.caches:
        self._add_error(
            SemanticError.duplicate_definition(
                kind="cache",
                name=cache.name,
                position=cache.meta,
            ),
        )
        return
    self._symbols.caches[cache.name] = cache
```

### Step 5: Update Code Generation

Add code generation in the appropriate visitor:

```python
def visit_cache_def(self, node: CacheDef, source_line: int | None) -> None:
    """Generate code for cache definition."""
    self._emitter.emit(
        f"_caches['{node.name}'] = Cache(",
        source_line=source_line,
    )
    self._emitter.indent()
    if node.ttl is not None:
        self._emitter.emit(f"ttl={node.ttl},")
    if node.size is not None:
        self._emitter.emit(f"size={node.size},")
    self._emitter.dedent()
    self._emitter.emit(")")
```

## Testing Grammar Changes

### Unit Tests

Create tests in `tests/dsl/grammar/`:

```python
def test_parse_cache_def():
    """Test parsing cache definition."""
    source = """
cache responses:
    ttl: 300 seconds
    size: 1000
"""
    tree = parse(source)
    assert tree is not None


def test_transform_cache_def():
    """Test transforming cache definition to AST."""
    source = """
cache responses:
    ttl: 300 seconds
"""
    tree = parse(source)
    ast = transform(tree)

    assert len(ast.statements) == 1
    cache = ast.statements[0]
    assert isinstance(cache, CacheDef)
    assert cache.name == "responses"
    assert cache.ttl == 300
```

### Manual Testing

Use the `dump-python` command to see generated code:

```bash
poetry run streetrace dump-python my_agent.sr
```

Use the `check` command to validate syntax:

```bash
poetry run streetrace check my_agent.sr
```

## Debugging Grammar Issues

### Ambiguity Errors

If Lark reports ambiguity, use the `ambiguity='explicit'` parser option to see all
possible parses:

```python
parser = Lark(
    grammar,
    parser="lalr",
    ambiguity="explicit",  # Shows all interpretations
)
```

### Viewing Parse Trees

Enable debug output in the parser:

```python
tree = parser.parse(source)
print(tree.pretty())  # Pretty-print the parse tree
```

### Common Issues

**Issue**: Rule not matching expected input

**Solution**: Check terminal priority and rule ordering. Higher priority terminals are
matched first.

**Issue**: Indentation errors

**Solution**: Verify `_INDENT` and `_DEDENT` placement matches the expected block
structure. Check that `_NL` appears before indented blocks.

**Issue**: Unexpected tokens in transformer

**Solution**: Use `_filter_children()` to remove noise tokens before processing.

## Grammar Style Guidelines

1. **Use lowercase for rules**: `model_def`, `flow_body`
2. **Use uppercase for terminals**: `NAME`, `STRING`, `MODEL`
3. **Prefix inline rules with `_`**: `_separator`, `_NL`
4. **Group related rules together**: All model rules, all flow rules, etc.
5. **Document complex rules**: Add comments explaining non-obvious patterns
6. **Keep rules focused**: One concept per rule when possible

## See Also

- [Architecture Overview](architecture.md) - Compiler pipeline overview
- [Extension Guide](extending.md) - Adding new features end-to-end
- [Lark Documentation](https://lark-parser.readthedocs.io/) - Full Lark reference
