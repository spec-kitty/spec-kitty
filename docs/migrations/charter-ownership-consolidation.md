---
title: Migration — Charter ownership consolidation
description: 'Migration for the charter-ownership consolidation whose shim was removed in 3.2.0: what changed and the steps required to move onto the consolidated ownership.'
doc_status: active
updated: '2026-06-03T00:00:00Z'
kind: How-To
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration — Charter ownership consolidation

**Status**: Shim removed in release 3.2.0. Migration required.

## What changed

The authoritative implementation of charter services lives under the top-level
`charter` package. The legacy `specify_cli.charter` package and its
submodules (`compiler`, `interview`, `resolver`) remain as thin re-export shims
for backward compatibility, with a `DeprecationWarning` on first import.

## Who is affected

Any downstream Python code that imports directly from `specify_cli.charter`:

- `from specify_cli.charter import build_charter_context, ensure_charter_bundle_fresh`
- `from specify_cli.charter.compiler import <X>`
- `from specify_cli.charter.interview import <X>`
- `from specify_cli.charter.resolver import <X>`

First-party code inside spec-kitty no longer uses these paths (three test files
are retained as deliberate compatibility exceptions per mission-internal
occurrence-map rules).

## What to do

Replace the import path:

| Old | New |
|-----|-----|
| `from specify_cli.charter import X` | `from charter import X` |
| `from specify_cli.charter.compiler import X` | `from charter.compiler import X` |
| `from specify_cli.charter.interview import X` | `from charter.interview import X` |
| `from specify_cli.charter.resolver import X` | `from charter.resolver import X` |

No call-site or signature changes are required — the re-exports are identity
re-exports, and the submodule shims alias `sys.modules` to the canonical module,
so the imported symbol is the same object.

## Timeline

- **3.1.x**: shims were functional; importing them emitted a
  single `DeprecationWarning` per process pointing at the caller.
- **3.2.0**: shim package removed. Imports from `specify_cli.charter` will
  raise `ModuleNotFoundError`.

## How to silence the warning temporarily

If you need to quiet the warning while you migrate, the standard `warnings`
module controls apply:

```python
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"specify_cli\.charter is deprecated.*",
    category=DeprecationWarning,
)
```

Prefer migrating over filtering — the filter will stop working in 3.2.0 because
the target module will be gone.

## Questions

File an issue against the `spec-kitty` repository with the `charter-migration`
label.
