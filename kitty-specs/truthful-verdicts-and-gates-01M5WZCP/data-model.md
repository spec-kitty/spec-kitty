# Data Model: Truthful verdicts and gates

No new entities. Changed invariants on existing ones:

- **Review-cycle record (approved)**: body = approval line; when a reviewer file is supplied, the approval line, a blank line, then the file's content. `reproduction_command` is a shell-valid argv (`shlex.join`). A supplied file never results in a reported durable write that lacks it.
- **Issue-matrix row**: at the `done` transition and in the consolidation terminality gate, any row with verdict `in-mission` is unresolved, regardless of whether its issue is a gating reference. Unchanged at `approved`.
- **safe-commit candidate set**: an explicitly named untracked file counts as a candidate whether or not it is ignored.
