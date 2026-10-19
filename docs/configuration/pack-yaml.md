---
title: 'pack.yaml reference'
description: 'Field reference for a Charter Pack pack.yaml descriptor: identity, lineage, the declared pack_level, requires_core and layout pointers, plus regenerate-graph --pack-root.'
doc_status: active
updated: '2026-10-11'
related:
- docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/configuration/index.md
---
# `pack.yaml` reference

Every Charter Pack carries an authored `pack.yaml` at its root. The model is
`PackDescriptor` (`src/charter/offering/packs/pack_descriptor.py`); unknown
fields are refused, and a field retired by an earlier release is refused with
`RETIRED_PACK_FIELD`. The generated `pack-manifest.yaml` is a separate file and
is never hand-edited.

## Fields

| Field | Required | Meaning |
|-------|----------|---------|
| `pack_id` | yes | Stable 26-character ULID identity. Minted once, never changed. |
| `name` | yes | Human-readable handle. Display only, not the identity. |
| `pack_version` | built-in only | Semantic version string. Required when `pack_level` is `built-in`; optional for `org` and `project`. |
| `parent_pack` | no | ULID of the pack this one extends. Omit or `null` for a root pack. |
| `pack_level` | yes (see below) | The tier the pack belongs to: `built-in`, `org` or `project`. |
| `requires_core` | no | PEP 440 version specifier of the Spec Kitty core versions the pack supports, for example `">=4.0,<5.0"`. An unparsable value is a schema error. Absent means no constraint (#6046). |
| `active_charter` | no | Pack-relative path to the active-charter file. Defaults to `org-charter.yaml` for an `org` pack. |
| `pack_drg` | no | Pack-relative path to the DRG source. Defaults per level: the sharded `*.graph.yaml` files at the root (`built-in`), `drg/fragment.yaml` (`org`), `graph.yaml` (`project`). |

`active_charter` and `pack_drg` must resolve inside the pack; an absolute path or a `..` escape is rejected by
`charter pack validate`.

## `pack_level`

The allowed values are the three tiers owned by `kernel.pack_tiers`. The
declared value must match the position the pack is configured at:

* **org packs:** a mismatch is refused when the pack is loaded
  (`PACK_LEVEL_MISMATCH`, attributed to `pack.yaml`). A `pack.yaml` that cannot
  be read or fails the schema is refused too.
* **built-in and project positions:** nothing refuses at load. The validator
  can report the mismatch when a caller passes the configured position
  (`validate_pack(..., expected_level=...)`), but `charter pack validate` on a
  bare path has no position, so it skips the mismatch check and still reports
  `PACK_LEVEL_MISSING` and schema faults.

**Deprecation window.** During the window a `pack.yaml` that omits `pack_level`
(or an org pack with no `pack.yaml`) still loads under the tier of the position
it is configured at, and reports a `PACK_LEVEL_MISSING` warning. After the
window the omission is a refusal. The `pack_level_backfill` upgrade migration
writes `pack_level: project` into an existing project pack.

## Regenerating a built-in pack's graph

`spec-kitty charter pack regenerate-graph [--check] --pack-root <dir>`
regenerates (or, with `--check`, verifies) the sharded `*.graph.yaml` fragments
and `pack-manifest.yaml` for a fetched copy of a **built-in-level** pack. The
root needs a valid `pack.yaml` declaring `pack_level: built-in`; org and project
packs are refused with exit 1 before anything is written, because the generators
would overwrite their `graph.yaml` or write a wrong manifest. Without the flag
the command targets the shipped built-in pack.
