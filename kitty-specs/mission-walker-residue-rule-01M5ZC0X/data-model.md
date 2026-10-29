# Data Model: Mission walkers share one residue rule

## Read-side classification of a `kitty-specs/` child

| Child | `meta.json` on disk | identity (`mission_id`) | marker tracked by git | Selection | `doctor identity` | `doctor mission-type` |
|---|---|---|---|---|---|---|
| fresh Mission (uncommitted) | yes | yes | no | listed | `pending` / `assigned` | audited |
| committed Mission | yes | yes | yes | listed | `pending` / `assigned` | audited |
| tracked legacy meta, no id | yes | no | yes | listed | `legacy` / `orphan` | audited |
| untracked meta, no id (git repo) | yes | no | no | — | `residue` | skipped |
| meta, no id, non-git root | yes | no | n/a | listed | `legacy` / `orphan` | audited |
| spec.md only (tracked or not) | no | — | any | — | `residue` | skipped |
| tracked meta deleted on disk (#6673) | no | — | yes | — | `residue` | skipped |
| lock / leftovers only | no | — | no | — | `residue` | skipped |
| non-directory (`README.md`) | — | — | — | — | not reported | not reported |

**Invariant (parity, FR-007):** listed by selection ⇔ `doctor identity` state ≠ `residue` ⇔ audited by `doctor mission-type` ⇔ agent candidate.

## `IdentityState.state`

`assigned | pending | legacy | orphan | residue`. The first four keep their FR-045 meaning for Missions. `residue` is set only by the walk, never by `classify_mission`.
