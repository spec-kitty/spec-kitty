# Contract: `agent tasks mark-status` resolution

Applies to `spec-kitty agent tasks mark-status <ID...> --status <s> [--wp WPxx]`.
Only the refusal surface changes in this mission; `--wp` semantics, the success
envelope and the event payload shape are unchanged.

## Resolution

For each requested id, `owners` is the sorted union of:

1. work packages whose authored `subtasks:` frontmatter lists the id, and
2. work packages whose structured `tasks.md` row lists the id (checkbox row,
   pipe-table row, or an inline `Subtasks:` list under a WP heading).

| Condition | Outcome |
| --- | --- |
| `owners == []` and id is not `WP<digits>`-shaped | `not_found` for that id (unchanged); the command fails only if nothing resolved |
| `owners == []` and id is `WP<digits>`-shaped | exit 1: `"<ID>: mark-status does not change work-package lanes. Use \`spec-kitty agent tasks move-task <WP_ID> --to <lane>\`."` and **no event** |
| `len(owners) > 1` and no `--wp` | exit 1: `"<ID> is a subtask of <A>, <B> in Mission <slug>; pass --wp to select one."` and **no event** (message unchanged from #5953) |
| `--wp` given and not in `owners` | exit 1: `"<ID> is not a subtask of <WP> in Mission <slug> (owners: …). Re-run with --wp …."` and **no event** (unchanged) |
| `len(owners) == 1` or `--wp in owners` | the id is attributed to `--wp` or the single owner |

`WP<digits>` ids that some WP authors as a subtask take the ambiguous/`--wp` rows
above; the lane-transition row applies only when no WP authors the id.

## Write

Exactly one `InnerStateChanged` annotation per affected WP:

- `wp_id` is the attribution from `## Resolution` — never re-derived from
  `tasks.md` order, filename order or a fresh roster lookup.
- An id that resolves but has no attribution refuses before the first event
  (`ValueError` surfaced as exit 1), so a batch never half-writes.
- A repeat of an already-satisfied value writes no event and reports
  `already_satisfied` (unchanged).
