# Data model: mark-status owner authority

No persisted schema changes. Three in-memory values carry the contract.

## Owner map

`authored_roster_owner_map(feature_dir) -> dict[WP_ID, frozenset[subtask_id]]`

- Built once per invocation from the authored `subtasks:` frontmatter of every
  `tasks/<WP>.md` file.
- Upper-cased ids; a WP file with no `subtasks:` key maps to an empty set (legacy
  WP); an unreadable roster raises (fail closed).

## Owner set (per requested id)

`owners(task_id) = sorted(set(roster_owners) | set(history_owners))`

- `roster_owners`: WPs whose authored roster lists the id.
- `history_owners`: WPs whose **structured** `tasks.md` row lists the id
  (checkbox row, pipe-table row, inline `Subtasks:` list under a WP heading).
  Prose mentions never contribute.
- Invariants: `len(owners) == 1` or the mark is refused/scoped; `owners` is sorted
  and de-duplicated so error messages are stable.

## Scoped mark

`(task_ids, status, wp)` → per-id `TaskIdResult` + `task_wps: dict[id, WP_ID]`

- `task_wps` is the **only** attribution the write path may read.
- A `WP`-shaped id (`WP\d+`) is a subtask id only when some WP authors it; then it
  obeys the same rules, else it is rejected as a lane transition.
- Invariant: every id in `updated` has exactly one entry in `task_wps`, or the
  command refuses before writing.

## Completion event

`InnerStateChanged` annotation: `{wp_id: WP_ID, delta: {subtasks: {id: value}}}`

- `wp_id` == `task_wps[id]`. Never derived from document order, filename order, or
  a second roster lookup.
- Grouped one event per WP per invocation (unchanged).
