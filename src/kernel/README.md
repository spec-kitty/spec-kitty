# kernel

Zero-dependency shared utilities for the spec-kitty ecosystem.

## What it is

`kernel` is a minimal, self-contained Python package that provides low-level utilities used by multiple modules in the spec-kitty stack:

- `specify_cli` — the main CLI tool
- `charter` — project governance and context building
- `doctrine` — agent profiles and mission configuration

Currently it contains:

- **`kernel.atomic`** — `atomic_write(path, content, *, mkdir=False)`: writes files atomically via a temp file + rename, preventing partial writes on crashes or power loss.
- **`kernel.glossary_types`** — canonical glossary primitive value types (`Strictness`, `ExtractedTerm`, `SemanticConflict`, `ScopeRef`, `GlossaryScope`); re-exported by `glossary` and `charter.offering.shared`.
- **`kernel.paths`** — `get_kittify_home()`, the `SPEC_KITTY_PACKS_ROOT`-aware built-in-pack-root primitive `get_built_in_pack_root()`, and the single-door `get_package_asset_root()` (which resolves `<built-in-pack-root>/missions` through that primitive): path resolution utilities used by both `specify_cli` and `charter`. `get_package_asset_root()` is the one canonical resolution body — `specify_cli.runtime.home.get_package_asset_root` is a thin delegate to it (FR-005, DR-1), not a second resolver.
- **`kernel.glossary_runner`** — plugin registry for the glossary runner. Defines `GlossaryRunnerProtocol`, `register()`, `get_runner()`, and `clear_registry()` (test-only; never called in production). Nobody registers eagerly: the consumer `charter.offering.missions.glossary_hook` lazily self-bootstraps the registry on first use (`get_runner()` → `None` → `import_module("glossary.attachment")` → `register(GlossaryAwarePrimitiveRunner)` → retry) and degrades only when `glossary.attachment` is unimportable; `doctrine` calls `get_runner()` without importing `specify_cli`.
- **`kernel.resolution`** — `resolve_rejecting_loops(path)` and `is_symlink_loop_error(exc)`: interpreter-invariant, loop-rejecting path resolution. Behaves exactly like non-strict `Path.resolve()` on every supported interpreter (3.11-3.14), except that a symlink loop anywhere in the path always raises `OSError(errno.ELOOP, ...)` — papering over CPython 3.13's removal of the post-realpath `stat()` probe that 3.11/3.12 relied on to surface loops (issue #3189).

## Why it exists

The spec-kitty codebase is structured as several distinct Python packages (`specify_cli`, `charter`, `doctrine`). These packages share common utilities, but none of them should depend on each other — that would create cyclic imports and tight coupling between layers that have different stability and deployment requirements.

`kernel` breaks this cycle by acting as a dependency floor: it has **no imports from any other spec-kitty package**, and every package that needs shared utilities imports from `kernel` instead of from each other.

```
        specify_cli
           ↓
        charter
           ↓
        doctrine
           ↓
        kernel    ← no spec-kitty imports here
```

## Preventing cyclic dependencies

The rule is simple: **`kernel` must never import from `specify_cli`, `charter`, or `doctrine`**.

If you find yourself needing to import from a higher-level package inside `kernel`, that is a signal that the utility belongs in the higher-level package, not in `kernel`. Keep `kernel` as a leaf node in the import graph.

## Stability contract

Because `kernel` is used by all layers of the stack, it is held to a higher stability standard than the packages that depend on it:

- All public functions must have full test coverage (`tests/kernel/`)
- The public API should remain stable across minor versions
- Breaking changes require bumping the major version

## Adding utilities

Only add to `kernel` if the utility:
1. Has no spec-kitty-specific dependencies
2. Is used (or will be used) by more than one package in the stack
3. Is general-purpose enough to be considered infrastructure
