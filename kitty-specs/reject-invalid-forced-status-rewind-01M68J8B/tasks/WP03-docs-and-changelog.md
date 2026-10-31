---
work_package_id: WP03
title: The operator-facing position
dependencies:
- WP01
requirement_refs:
- FR-010
- SC-006
- C-002
- C-004
planning_base_branch: issue-6514-reject-invalid-forced-status-rewind
merge_target_branch: issue-6514-reject-invalid-forced-status-rewind
branch_strategy: Planning artifacts for this mission were generated on issue-6514-reject-invalid-forced-status-rewind. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6514-reject-invalid-forced-status-rewind unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reject-invalid-forced-status-rewind-01M68J8B
base_commit: b8ec1ded213719faacdf3178ddc86cf701eac2c4
created_at: '2026-10-31T10:22:47.624352+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 3 - Operator position
history:
- at: '2026-10-31T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/status-model.md
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/architecture/status-model.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6514'
---
# Work Package Prompt: WP03 – The operator-facing position

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

`docs/architecture/status-model.md` is the operator reference for this model. It must
state (a) that a forced rewind out of `for_review` requires a `review_ref` and that force
does not override it, and (b) what an operator may do about rows written before the fix —
without promising a repair the CLI does not ship.

Done when a reader of the guard table and of the force-override paragraph cannot come away
believing that `--force` alone can produce this transition, and the changelog carries the
`[Unreleased]` entry with `(#6514)`.

## Context & Constraints

- Spec FR-010, SC-006, C-002, C-004. Contract `contracts/forced-rewind-refusal.md` C-1..C-5.
  Research §5 D-1..D-6.
- **Say what ships.** This mission adds a refusal and nothing else. Do not describe a
  `status repair`/`status doctor --fix` for event rows: neither exists (D-5). Describe the
  no-rewrite rule and the append-only route a maintainer may author, and say plainly that
  no automatic correction is provided.
- **Do not regenerate the whole CLI reference.** `docs/api/agent-subcommands.md` is
  generated and the installed CLI's global asset cache is shared with other concurrent
  agents (mission brief, "Shared machine state"). The `--review-ref` help text is not
  changing, so no CLI-reference regeneration is needed. Verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0) instead.
- **Changelog shape**: `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink),
  under `[Unreleased]`, bold impact-first lead with `(#6514)`, before/after, under 1,200
  characters.

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`

Implement with `spec-kitty agent action implement WP03 --agent pi --mission reject-invalid-forced-status-rewind-01M68J8B`.

## Subtasks & Detailed Guidance

### T009 – `docs/architecture/status-model.md`

Three edits, kept where a reader already looks:

1. **The transition-matrix comment block / force-override paragraph** (around
   `**Force override**: Any transition can be forced with ...`): add the one exception, so
   "any transition can be forced" is not read as "any event can be written".
2. **The Guard Conditions table**: one new row —
   `| for_review -> in_progress (forced) | review_ref required (force does not override) | "Transition for_review -> in_progress requires review_ref: ..." |`
   — using the shipped message's leading text so the table does not drift from the code.
3. **A short subsection** (after the guard table, before "Migration Phases") titled
   something like "Forced rewinds out of review": what the edge is, why it is force-only,
   what `move-task` supplies (`force-override`), what the generic doors must supply, and
   **"Rows written before this refusal"** stating: the row is permanent and `status
   validate` will keep reporting it; bytes are never rewritten; there is no automatic
   repair; a maintainer may author an append-only correction (preserving the original
   record) if a mission needs the finding cleared, and should record why.

Keep the page's existing voice and ASCII-diagram conventions; no marketing prose.

Commit: `docs(6514): the forced for_review rewind requires a review_ref`.

### T010 – Changelog entry

Add under `[Unreleased]` → `### Fixed` (create the section only if absent, matching the
file's existing heading style):

> **A forced status rewind out of review can no longer append an event the status
> validator rejects, so a successful command can no longer leave a mission's ledger
> permanently invalid** (#6514). **Before:** `spec-kitty agent status emit WP01 --to
> in_progress --force --reason "<why>"` on a work package in `for_review` exited 0 and
> appended a `for_review → in_progress` event with `review_ref: null`; `spec-kitty agent
> status validate` then failed on that same event with `for_review->in_progress without
> review_ref`, and because the log is append-only the row could not be removed. **After:**
> the requirement has one owning definition in the work-package state machine, so the
> refusal happens at validation time — before anything is written — on every write door
> (`agent status emit`, `orchestrator-api wp transition`). The refused command exits
> non-zero, names `review_ref`, leaves `status.events.jsonl` and `status.json`
> byte-identical, and `--force --reason` still works when a real `--review-ref` is
> supplied. `move-task`'s forced rewind, which supplies its `force-override` sentinel, is
> unchanged.

Commit: `docs(6514): changelog the forced-rewind refusal`.

### T011 – Gates

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run python -m scripts.docs.check_changelog_style
uv run pytest -q tests/architectural/test_no_legacy_terminology.py
```

`check_docs_freshness --ci` must report `errors=0`. `check_changelog_style` must pass on the
new entry (it enforces the lead/reference/before-after shape and the length bound). Do not
add a gate that does not exist to make the list look thorough. If a docs gate fails because another
concurrent agent rewrote the shared CLI asset cache, say so in the WP history note and in
the PR's `## Deferred` — do not "fix" it by mass-regenerating the reference.

## Definition of Done

- The guard table lists the requirement; the force-override paragraph no longer reads as
  "any transition, no strings attached".
- The historical-row position is stated honestly, with no invented command.
- `check_docs_freshness --ci` errors=0.
