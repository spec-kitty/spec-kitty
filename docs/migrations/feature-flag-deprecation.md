---
title: 'Migration: --feature to --mission'
description: 'Migration from the --feature flag to --mission, deprecated in mission 077 and fully removed as of 3.2.3 (#1060): the timeline and the required call-site changes.'
doc_status: active
updated: '2026-07-20'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: `--feature` to `--mission`

**Status**: Deprecated as of Mission `077-mission-terminology-cleanup`.
**Full removal (3.2.3, #1060)**: the alias has been **hard-removed from every
user-facing and internal/agent command**, including the eight commands that
previously kept it during the deprecation window (`implement`, `merge`,
`next`, `research`, `context`, `accept`, `lifecycle plan`/`lifecycle tasks`,
`mission-type current`) and the internal/agent command cluster (`agent
status/tasks/action/context/mission`, `charter lint`, `materialize`,
`validate-encoding`, `validate-tasks`, `verify`/`verify-setup`) removed
earlier in 3.2.x (#1060-A). `--feature` is no longer accepted anywhere —
passing it exits with code 2 and "No such option: --feature".

## Why This Change

The `--feature` CLI flag has been replaced by `--mission` as the canonical
selector for tracked missions. This aligns the operator-facing CLI with the
canonical terminology boundary:

- **Mission Type** = reusable workflow blueprint (`software-dev`, `research`, `documentation`)
- **Mission** = concrete tracked item under `kitty-specs/<mission-slug>/`
- **Mission Run** = runtime/session execution instance only

`--feature` is no longer available anywhere, including the top-level commands
that kept it as a hidden deprecated alias during the migration window. All
first-party surfaces have moved to `--mission`.

## What Changed

| Before | After |
| --- | --- |
| `spec-kitty mission current --feature 077-foo` | `spec-kitty mission current --mission 077-foo` |
| `spec-kitty next --feature 077-foo` | `spec-kitty next --mission 077-foo` |
| `spec-kitty agent tasks status --feature 077-foo` | `spec-kitty agent tasks status --mission 077-foo` (the `--feature` form is now **removed** — it errors) |

`--feature` is rejected everywhere with "No such option: --feature" — there is
no remaining command where it resolves, warns, or is merely hidden from
`--help`.

## Behavioral Changes

Any `--feature` occurrence, on any command, is now a parser error. The
command exits before selector resolution with exit code 2.

## How to Migrate Scripts

Replace `--feature` with `--mission` anywhere you invoke `spec-kitty`.

```bash
# Old
spec-kitty mission current --feature 077-mission-terminology-cleanup

# New
spec-kitty mission current --mission 077-mission-terminology-cleanup
```

For bulk shell-script migration:

```bash
find . -name "*.sh" -o -name "*.bash" | xargs sed -i '' 's/--feature /--mission /g'
```

Review the diff before committing. A blind replacement can catch unrelated tools
or documentation.

## Suppressing the Warning During Cutover (historical)

`SPEC_KITTY_SUPPRESS_FEATURE_DEPRECATION` was used to silence the deprecation
warning during the alias window. Now that `--feature` is fully removed
(3.2.3, #1060), the variable is **inert** — it is accepted but has no effect, since
there is no warning left to suppress. See
[Environment Variables](../api/environment-variables.md) for the current
state.

## Removal (complete)

`--feature` was removed everywhere in 3.2.3 (#1060). This section previously
listed forward-looking removal criteria; they are retained here only for
historical record of what gated the removal:

1. First-party doctrine skills, examples, and user-facing docs teach `--mission` only.
2. First-party machine-facing surfaces completed Scope B alignment.
3. A documented audit window showed zero first-party legacy `--feature` usage in active CI and shipped scripts.

## References

- [Mission spec](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/077-mission-terminology-cleanup/spec.md)
- [Mission Type / Mission / Mission Run Terminology Boundary ADR](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md)
- [Mission Nomenclature Reconciliation initiative](https://github.com/spec-kitty/spec-kitty/blob/main/docs/plans/initiatives/2026-04-mission-nomenclature-reconciliation/README.md)
- [Tracking issue #241](https://github.com/Priivacy-ai/spec-kitty/issues/241)
