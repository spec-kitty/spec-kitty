---
title: 'ADR: Glossary Primitive Type Ownership and the Kernel Package'
description: Relocates stdlib-only glossary value types into the kernel package so doctrine stops importing from specify_cli and the container dependency direction holds.
status: Accepted
date: '2026-03-25'
doc_status: active
kind: ADR
updated: '2026-03-25T00:00:00Z'
---

## Context

`src/doctrine/missions/primitives.py` and `src/doctrine/missions/glossary_hook.py` imported
types from `specify_cli.glossary.*` at module level, violating the stated architectural rule
that `doctrine` has no dependency on `specify_cli`.

The types involved were pure value objects with no external dependencies:
- `Strictness` — enforcement level enum
- `ExtractedTerm` — term extracted from input text
- `SemanticConflict` + nested types (`TermSurface`, `ConflictType`, `Severity`, `SenseRef`)
- `ScopeRef` + `GlossaryScope`

These were defined in `specify_cli.glossary.*` for historical reasons, but their nature
(stdlib-only, zero external dependencies) makes them candidates for the lowest layer.

A `src/kernel/` package had already been introduced to hold `atomic.py` — a write utility
shared by all three higher-level packages. Its declared contract is:

```
kernel  <-  doctrine
kernel  <-  charter
kernel  <-  specify_cli
```

---

## Options Considered

| Option | Location | Verdict |
|--------|----------|---------|
| A | `src/doctrine/shared/glossary_types.py` | Doctrine becomes the owner; specify_cli imports from doctrine. Establishes the right direction but places glossary contracts in a domain-specific package. |
| B | Accept the dependency; add specify_cli to doctrine/pyproject.toml | Abandons the standalone-doctrine goal. Rejected. |
| C | `src/kernel/glossary_types.py` | Zero-dependency types belong in the zero-dependency layer. All three higher packages import from kernel. |

---

## Decision

**Option C: move to `src/kernel/glossary_types.py`.**

The types are stdlib-only value objects with no domain-specific behavior. They are not
"doctrine primitives" — they are shared primitive types used by the glossary subsystem across
all containers. The kernel is the designated home for exactly this category of artifact.

For `glossary_hook.py`: `GlossaryAwarePrimitiveRunner` and `read_glossary_check_metadata`
orchestrate `specify_cli`'s full glossary pipeline and cannot move to kernel or doctrine
without inverting the ownership of the entire pipeline. The import is deferred to call time
(lazy import inside the function body). `Strictness` now imports from `kernel.glossary_types`.
This is the only sanctioned lazy cross-boundary import in the codebase.

Backward compatibility is preserved via re-exports:
- `doctrine.shared` re-exports all types from `kernel.glossary_types`
- `specify_cli.glossary.{strictness,extraction,models,scope,checkpoint}` re-export their
  respective types from `kernel.glossary_types`

No existing call sites require changes.

---

## Consequences

### Dependency graph (after)

```
kernel (stdlib only)
  |
  +-- doctrine (no dependency on specify_cli)
  |     doctrine.shared re-exports kernel.glossary_types
  |     doctrine.missions.primitives imports from kernel.glossary_types
  |     doctrine.missions.glossary_hook: kernel for Strictness; lazy import for specify_cli
  |
  +-- charter (no dependency on specify_cli at module level)
  |
  +-- specify_cli
        specify_cli.glossary.* re-exports from kernel.glossary_types
        All existing import paths continue to work unchanged
```

### Class identity

`from specify_cli.glossary.strictness import Strictness`,
`from doctrine.shared import Strictness`, and
`from kernel.glossary_types import Strictness`
all return the same class object. `isinstance` checks across package boundaries work.

### Isolation test

`tests/doctrine/test_isolation.py` verifies that `doctrine.missions.primitives` can be
imported with only `doctrine` and `kernel` on `PYTHONPATH` — `specify_cli` absent.

### kernel package purpose (expanded)

`src/kernel/` now contains two modules:
- `atomic.py` — atomic file-write utility
- `glossary_types.py` — shared glossary primitive types

Future zero-dependency shared utilities and value types belong here rather than being
duplicated across or imported between higher-level packages.

---

## Related

- PR #305 review finding C1
- `docs/development/pr305-review-resolution-plan.md` — Track 2
- `src/kernel/__init__.py` — package declaration
- `src/kernel/glossary_types.py` — canonical type definitions
