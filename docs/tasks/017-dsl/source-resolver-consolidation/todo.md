# Implementation Plan: Source Resolver Consolidation

## Phase 1: Extend SourceResolver ✓

- [x] Add `format` field to `SourceResolution`
- [x] Add `_detect_format()` method (extension for files, MIME for HTTP)
- [x] Add `_is_excluded()` method with exclusion set
- [x] Add `discover(locations: list[Path]) -> dict[str, SourceResolution]`
- [x] Add security policy: reject HTTP for .py extensions (DSL and YAML allowed)
- [x] Add unit tests for SourceResolver extensions

## Phase 2: Update Loaders

- [ ] Change `load()` signature: `load(resolution: SourceResolution) -> WorkloadDefinition`
- [ ] DslDefinitionLoader: use `resolution.content`, remove discovery code
- [ ] YamlDefinitionLoader: use `resolution.content`, remove discovery code
- [ ] PythonDefinitionLoader: use `resolution.file_path`, remove discovery code
- [ ] Remove from all loaders:
  - [ ] `discover()`
  - [ ] `load_from_url()`
  - [ ] `load_from_source()`
  - [ ] `_resolve_path()`
  - [ ] `_is_excluded_path()`
- [ ] Update loader unit tests

## Phase 3: Update WorkloadManager

- [ ] Create `SourceResolver` instance in `__init__` (with http_auth only, not search_locations)
- [ ] Change `_loaders` dict to be keyed by format: `{"dsl": ..., "yaml": ..., "python": ...}`
- [ ] Update `discover_definitions()` to:
  - Keep location priority loop (domain logic stays in manager)
  - Call `resolver.discover(paths)` for each location
  - Use `resolution.format` to select loader
- [ ] Update `_load_definition_from_identifier()` to use `resolver.resolve()`
- [ ] Remove:
  - [ ] `_discover_in_location()` (replaced by resolver.discover)
  - [ ] `_find_workload_files()` (no longer needed)
  - [ ] `_get_definition_loader()` (replaced by format-keyed lookup)
- [ ] Keep:
  - [ ] `_compute_search_locations()` (domain-specific logic)
  - [ ] `SEARCH_LOCATION_SPECS` (domain-specific config)
- [ ] Update manager unit tests

## Phase 4: Protocol and Cleanup

- [ ] Update `DefinitionLoader` protocol in `loader.py`:
  - Remove `discover()`, `load_from_url()`, `load_from_source()`
  - Keep `load(resolution: SourceResolution) -> WorkloadDefinition`
  - Keep `can_load()` or remove if no longer needed
- [ ] Update `docs/testing/workloads/loading-matrix.md`
- [ ] Run `make check`
- [ ] Verify `--list-agents` works
- [ ] Verify `--agent=Streetrace_Coding_Agent` works
- [ ] Verify `--agent=./agents/test.sr` works
