# Task: Consolidate Source Resolution in SourceResolver

**Date**: 2026-01-26
**Feature**: 017-dsl
**Status**: Draft

## Problem

Discovery and resolution logic is duplicated across loaders:

```
Current:
┌─────────────────┐
│ WorkloadManager │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐ ┌────────┐
│DslLdr │ │YamlLdr│ │ PyLdr  │
├───────┤ ├───────┤ ├────────┤
│discover│ │discover│ │discover│  ← duplicated
│load    │ │load    │ │load    │
│load_url│ │load_url│ │load_url│  ← duplicated
│_resolve│ │_resolve│ │_resolve│  ← duplicated
│_exclude│ │_exclude│ │_exclude│  ← duplicated
└───────┘ └───────┘ └────────┘
```

Each loader has ~150 lines of discovery/resolution code that's format-independent.

## Solution

Centralize discovery and resolution in `SourceResolver`. Loaders only load from `SourceResolution`.

```
Proposed:
┌─────────────────┐
│ WorkloadManager │
└────────┬────────┘
         │
         ▼
┌────────────────┐
│ SourceResolver │
├────────────────┤
│ discover()     │  ← one implementation
│ resolve()      │  ← one implementation
│ format detect  │  ← extension or MIME
│ security policy│  ← HTTP restrictions
└───────┬────────┘
        │ SourceResolution
        │ (content, path, format)
        ▼
   ┌────┴────┐
   ▼         ▼
┌───────┐ ┌───────┐ ┌────────┐
│DslLdr │ │YamlLdr│ │ PyLdr  │
├───────┤ ├───────┤ ├────────┤
│load() │ │load() │ │load()  │  ← uses content
│       │ │       │ │        │  ← uses path
└───────┘ └───────┘ └────────┘
```

## Design

### SourceResolution (extended)

```python
@dataclass
class SourceResolution:
    content: str
    source: str
    source_type: SourceType
    file_path: Path | None = None
    content_type: str | None = None
    format: str | None = None  # NEW: "dsl", "yaml", "python"
```

### SourceResolver (extended)

```python
class SourceResolver:
    SEARCH_LOCATIONS = [
        ("cwd", ["./agents", ".streetrace/agents"]),
        ("home", ["~/.streetrace/agents"]),
        ("bundled", []),  # computed from package
    ]

    EXCLUDED_DIRS = {".venv", ".git", ".github", "node_modules", "__pycache__"}

    def discover(self, locations: list[Path]) -> dict[str, SourceResolution]:
        """Discover all agents in locations, return name -> resolution mapping."""

    def resolve(self, identifier: str, ...) -> SourceResolution:
        """Resolve identifier to content with format detection."""

    def _detect_format(self, path: Path | None, content_type: str | None) -> str:
        """Detect format from extension or MIME type.

        Files: .sr → dsl, .yaml/.yml → yaml, directory with agent.py → python
        HTTP: application/yaml, text/yaml → yaml, else → dsl
        """

    def _is_excluded(self, path: Path) -> bool:
        """Check if path should be excluded from discovery."""
```

### Format Detection Rules

| Source | Detection Method | Result |
|--------|-----------------|--------|
| File `.sr` | Extension | `"dsl"` |
| File `.yaml` / `.yml` | Extension | `"yaml"` |
| Directory with `agent.py` | Structure | `"python"` |
| HTTP `application/yaml` | MIME type | `"yaml"` |
| HTTP `text/yaml` | MIME type | `"yaml"` |
| HTTP other | Default | `"dsl"` |

### Security Policy

| Format | HTTP Allowed | Enforced In |
|--------|--------------|-------------|
| YAML | Yes | SourceResolver |
| DSL | Yes | SourceResolver |
| Python | No | SourceResolver |

### Simplified Loaders

Remove from each loader:
- `discover()` → moved to SourceResolver
- `load_from_url()` → handled by SourceResolver
- `load_from_source()` → handled by SourceResolver
- `_resolve_path()` → in SourceResolver
- `_is_excluded_path()` → in SourceResolver

Keep:
- `load(resolution: SourceResolution) -> WorkloadDefinition`
- Format-specific parsing logic

```python
class DslDefinitionLoader:
    def load(self, resolution: SourceResolution) -> DslWorkloadDefinition:
        """Load DSL from resolution.content."""

class YamlDefinitionLoader:
    def load(self, resolution: SourceResolution) -> YamlWorkloadDefinition:
        """Load YAML from resolution.content."""

class PythonDefinitionLoader:
    def load(self, resolution: SourceResolution) -> PythonWorkloadDefinition:
        """Load Python from resolution.file_path (requires import)."""
```

### WorkloadManager Changes

WorkloadManager keeps `search_locations` logic (domain-specific: cwd, home, bundled)
but delegates file discovery to SourceResolver. Loaders lose their `discover()` method.

```python
class WorkloadManager:
    def __init__(self, ...):
        # Keep search_locations computation (domain-specific)
        self.search_locations = self._compute_search_locations()

        # Create resolver with http_auth for HTTP resolution
        self.resolver = SourceResolver(http_auth=http_auth)

        # Loaders keyed by format, not extension
        self._loaders = {
            "dsl": DslDefinitionLoader(),
            "yaml": YamlDefinitionLoader(),
            "python": PythonDefinitionLoader(),
        }

    def discover_definitions(self) -> list[WorkloadDefinition]:
        """Delegate discovery to SourceResolver, then load with appropriate loader."""
        definitions = []
        seen_names: set[str] = set()

        # Process locations in priority order (first match wins)
        for location_name, paths in self.search_locations:
            resolutions = self.resolver.discover(paths)
            for name, resolution in resolutions.items():
                if name not in seen_names:
                    seen_names.add(name)
                    loader = self._loaders[resolution.format]
                    definition = loader.load(resolution)
                    definitions.append(definition)
        return definitions

    def _load_definition_from_identifier(self, identifier: str) -> WorkloadDefinition:
        """Use resolver for identifier→content, then loader for parsing."""
        resolution = self.resolver.resolve(identifier)
        loader = self._loaders[resolution.format]
        return loader.load(resolution)
```

Key architectural decision: WorkloadManager does NOT instantiate SourceResolver with
search_locations. Instead, it passes locations to `resolver.discover(paths)` per call.
This keeps domain logic (location priority) in WorkloadManager while delegating
file discovery to SourceResolver.

## Implementation Plan

### Phase 1: Extend SourceResolver

- [ ] Add `format` field to `SourceResolution`
- [ ] Add `_detect_format()` method
- [ ] Add `_is_excluded()` method with exclusion logic
- [ ] Add `discover(locations)` method
- [ ] Add security policy for HTTP (reject .sr, .py)
- [ ] Add tests for new functionality

### Phase 2: Update Loaders

- [ ] Change `load()` signature to accept `SourceResolution`
- [ ] DslLoader: use `resolution.content`
- [ ] YamlLoader: use `resolution.content`
- [ ] PythonLoader: use `resolution.file_path`
- [ ] Remove `discover()`, `load_from_url()`, `load_from_source()`, `_resolve_path()`, `_is_excluded_path()`
- [ ] Update tests

### Phase 3: Update WorkloadManager

- [ ] Replace `_definition_loaders` dict with format-keyed `_loaders`
- [ ] Use `SourceResolver.discover()` in `discover_definitions()`
- [ ] Use `SourceResolver.resolve()` in `_load_definition_from_identifier()`
- [ ] Remove duplicated location/exclusion logic
- [ ] Update tests

### Phase 4: Cleanup

- [ ] Remove `DefinitionLoader` protocol methods that moved to SourceResolver
- [ ] Update `docs/testing/workloads/loading-matrix.md`
- [ ] Run `make check`

## Files to Modify

| File | Changes |
|------|---------|
| `src/streetrace/agents/resolver.py` | Add discover, format detection, exclusions |
| `src/streetrace/workloads/dsl_loader.py` | Simplify to load from SourceResolution |
| `src/streetrace/workloads/yaml_loader.py` | Simplify to load from SourceResolution |
| `src/streetrace/workloads/python_loader.py` | Simplify to load from SourceResolution |
| `src/streetrace/workloads/manager.py` | Use SourceResolver for discovery/resolution |
| `src/streetrace/workloads/loader.py` | Update DefinitionLoader protocol |

## Success Criteria

1. All tests pass
2. `make check` passes
3. Each loader is <100 lines (currently ~200-400)
4. Discovery/resolution logic exists in exactly one place
5. `--list-agents` and `--agent=NAME` work as before
