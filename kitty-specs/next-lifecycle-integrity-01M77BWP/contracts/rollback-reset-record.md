# Contract: rollback reset record and `--reset-subtasks`

## CLI
`spec-kitty agent tasks move-task <WP> --to planned [--reset-subtasks T001,T002 --note "<why>"]`
- **Without `--reset-subtasks`:** the full reset (unchanged default).
- **With `--reset-subtasks`:** only the named ids reset. The move is refused before any write when:
  - no `--note`/`--reason` is given;
  - an id is not on the WP roster;
  - the target lane is not `planned`.

## Status event
The PLANNED transition's `policy_metadata.rollback_reset` (see `data-model.md`).

## Output
- **Human line:** adds the scope (`full` or `narrowed`) and the reason.
- **JSON:** adds `subtasks_reset_scope` and `subtasks_reset_reason`. The existing `subtasks_reset_*` fields are unchanged.
