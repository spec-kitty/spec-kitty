---
title: 'Migration: --mission to --mission-type'
description: 'Migration from --mission to --mission-type, deprecated in mission 077: why the rename, the condition-gated removal (no calendar date), and the required changes.'
doc_status: active
updated: '2026-06-03'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: `--mission` to `--mission-type`

**Status**: Deprecated as of Mission `077-mission-terminology-cleanup`.
**Removal**: Gated on named conditions. No calendar date is set.

## Why This Change

On a small set of blueprint-selection commands, `--mission` used to mean
"mission type" instead of "tracked mission slug". That created an inverse-drift
bug because `--mission` means tracked mission everywhere else in the main CLI.

Those blueprint-selection sites now use `--mission-type` as the canonical flag.
`--mission` remains available only as a hidden deprecated alias on those sites
during the migration window.

This applies to the inverse-drift command family:

- `spec-kitty agent mission create`
- `spec-kitty charter interview`
- `spec-kitty lifecycle specify`
- any additional first-party blueprint selector updated as part of Mission 077

## What Changed

| Before | After |
| --- | --- |
| `spec-kitty agent mission create new-thing --mission software-dev` | `spec-kitty agent mission create new-thing --mission-type software-dev` |
| `spec-kitty charter interview --mission research` | `spec-kitty charter interview --mission-type research` |
| `spec-kitty specify new-thing --mission software-dev` | `spec-kitty specify new-thing --mission-type software-dev` |

## Behavioral Changes

1. `--mission-type` is the only advertised flag in `--help` output.
2. `--mission` still works on these sites, but emits exactly one deprecation warning.
3. Passing both flags with different values fails deterministically and names both values in the error.

## How to Migrate Scripts

Replace blueprint-selector uses of `--mission` with `--mission-type`.

```bash
# Old
spec-kitty agent mission create new-thing --mission software-dev

# New
spec-kitty agent mission create new-thing --mission-type software-dev
```

## Suppressing the Warning During Cutover

If you need to silence the deprecation warning temporarily while cutting over:

```bash
export SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION=1
```

This suppresses the warning only. Conflict detection remains active.

## Removal Criteria

The deprecated inverse alias can be removed only when:

1. First-party docs and skills use `--mission-type` consistently for blueprint selection.
2. All inverse-drift compatibility tests are green without relying on the alias.
3. A documented audit window shows zero first-party scripted usage of `--mission` for blueprint selection.

Removal is a separate follow-up change, not part of Mission 077.

## References

- [Mission spec](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/077-mission-terminology-cleanup/spec.md)
- [Mission Type / Mission / Mission Run Terminology Boundary ADR](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md)
- [Tracking issue #241](https://github.com/Priivacy-ai/spec-kitty/issues/241)
