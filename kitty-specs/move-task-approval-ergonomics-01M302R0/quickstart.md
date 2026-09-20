# Quickstart: what changes for an operator (#3469)

After this mission lands, the WP approval workflow stops forcing false records and accepts natural
flag names.

## Issue-matrix: context-only citations no longer force a false verdict

Before: a `spec.md` citing a parent epic, sibling missions, or a `PR #NNNN` scaffolded a **gating**
row for each, and you had to pick a false verdict (`fixed` / `in-mission` / …) to pass approval.

After:
- Context-only citations (lines marked `parent`, `epic`, `see #`, `Follow-up:`, `baseline-red`) and
  `PR #NNNN` references are classified **non-gating** — they do not block the `approved` transition.
- Any residual or operator-recorded row can carry the new truthful verdict:

  ```bash
  spec-kitty agent issue-verdict --mission <handle> --issue 1234 \
    --verdict not-applicable --actor claude \
    --evidence-ref "Cited as context in spec.md; mission owes no work."
  ```

- `not-applicable` is **terminal** — it also passes the merge/`done` gate; you never re-verdict it.
- **Fail-safe preserved**: an unmarked bare `#1234` in prose still gates — the gate only relaxes on an
  explicit signal, so real implementation targets are never silently skipped.

## move-task: natural flag names now work

```bash
# Both forms are now equivalent:
spec-kitty agent tasks move-task WP01 --to doing --actor claude --reason "starting WP01"
spec-kitty agent tasks move-task WP01 --to doing --agent  claude --note   "starting WP01"
```

## Subtask completion: use mark-status, not checkboxes

Ticking `- [x]` in `tasks.md` does **not** move the `for_review` gate (subtask completion is
event-sourced by design). Complete subtasks with:

```bash
spec-kitty agent tasks mark-status T0NN --status done --mission <handle>
```

The move-task guidance and `issue-verdict --help` now state these rules up front, and the
specify/plan/tasks/analyze prompts warn early that approvals gate on issue-matrix verdicts.
