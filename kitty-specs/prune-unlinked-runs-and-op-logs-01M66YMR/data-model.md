# Data Model — retention links, verdicts and the report vocabulary

The engine has no database. Its model is: one **item** (a deletable unit on disk),
the thing it **links** to (a Mission, an Op, or nothing), and one **verdict** with
exactly one reason. Everything below is the vocabulary `doctor event-logs` reports.

## Item

| Field | Type | Meaning |
| --- | --- | --- |
| `surface` | registry surface name | which state surface the item belongs to (`runtime_run_event_log`, `glossary_fallback_events`, `derived_mission_views`). Unchanged. |
| `kind` | `run` \| `mission_log` \| `op_log` \| `cache` | the family the item is ranked in. `op_log` is new. |
| `path` | project-relative POSIX path | the item. Unchanged. |
| `mission` | Mission directory name \| `null` | the Mission the item links to, when it links to one. Never set for an Op log. |
| `age_days` | float, 2 dp | age of the newest content file (lock sidecars excluded). Unchanged. |
| `reason` | string | why the item is a candidate or kept. New values below. |

## Link state (new)

Every item resolves one link state before its verdict. Today the engine has two
states (resolved, or `Mission not found`); the model needs three.

| State | Meaning | Examples |
| --- | --- | --- |
| **owned** | The item names an owner this checkout resolves. | A run linked through the run index; a run whose snapshot names its Mission by slug; a mission log whose stem is a known Mission id; an Op log whose Op record is present. |
| **unlinked** | The item names no owner at all. | A run whose index entry is gone and whose snapshot records no Mission identity; an Op log whose Op has no record in this checkout. |
| **unknown** | The item records an identity this checkout cannot resolve (no Mission, or more than one). | A run whose recorded `mission_id` or slug matches no `kitty-specs/` directory, or matches two; a mission log stem that sanitizes to two Missions. |

Rules:

1. **Identity.** A recorded `mission_id` is the only runtime identity; a slug is
   read only from a record that carries no `mission_id`. A run snapshot records no
   identity at the top level in the production writer, so its recorded input slug
   (`inputs.mission_slug`) is its slug record — an application of the existing rule,
   not a widening of it.
2. **Unreadable is unknown.** A snapshot that is missing, not JSON, or not an object
   reads as `unknown`, never as `unlinked` (fail safe).
3. **Ambiguity is unknown.** An identity claimed by two Mission directories is never
   resolved first-match-wins.
4. **An Op log's owner is its Op.** The Op id is the log stem less the
   `profile-invocation-` prefix. The Op is *open* while `kitty-ops/<id>.jsonl` exists,
   carries no `completed` event, and the id is not on the closure spine
   `kitty-ops/op-closures.jsonl`. There is no `unknown` state for an Op: a missing
   record means no trace of that Op exists here.
5. **Op-scoped logs are recognised by prefix**; `_cli` / `_renderer` logs (which name
   no owner by design) are still never collected.

## Verdict order (first match wins)

| # | Condition | Verdict | Reason |
| --- | --- | --- | --- |
| 1 | rank < `keep_runs` (within its family) | kept | `within keep_runs` |
| 2 | `age_days` ≤ `max_age_days` | kept | `younger than max_age_days` |
| 3 | link is **unknown** | kept | `Mission not found` |
| 4 | link is **unlinked** (ledger items) | candidate | `past retention; no Mission recorded` (run) / `past retention; no Op recorded` (Op log) |
| 5 | owner's work is not over | kept | `Mission is open` / `Op is open` |
| 6 | a lock is held (run cursor lock / writers' event-log lock) | kept | `lock held` |
| 7 | otherwise | candidate | `past retention; Mission completed` / `past retention; Op completed` |

Rebuildable caches keep their own two-step rule (`rebuildable cache`, or `lock
held`). Deleting requires **both** limits exceeded (steps 1 and 2), exactly as today.

## Work-over facts

| Family | Work is over when |
| --- | --- |
| run | its Mission is merged, **or** the run's own journal records `MissionRunCompleted` |
| mission log | its Mission is completed (merged, or every WP terminal) |
| op log | its Op is closed (completion event in the record, or a closure on the spine) |

## Report vocabulary (additive)

New `kind`: `op_log`.
New reasons: `past retention; no Mission recorded`, `past retention; Op completed`,
`past retention; no Op recorded`, `Op is open`.
Removed reasons: none. Re-worded reasons: none. New top-level keys: none.

## Deletion

Unchanged: a run through `_delete_run` (index entries dropped under the run-cursor
lock and the index lock, snapshot unlinked, directory removed by the tool-owned tree
door); a glossary log through `_delete_locked_log` (unlink under the writers'
event-log lock, its lock and sidecars stay). Op logs reuse the glossary deleter, so
the deleted unit is one file, never a directory, and the Op record and index are
untouched.
