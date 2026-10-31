---
work_package_id: WP03
title: Changelog and recovery docs for the cleared record
dependencies:
- WP02
requirement_refs:
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6770-consolidate-rerun-fresh-baseline
merge_target_branch: issue-6770-consolidate-rerun-fresh-baseline
branch_strategy: Planning artifacts for this mission were generated on issue-6770-consolidate-rerun-fresh-baseline. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6770-consolidate-rerun-fresh-baseline unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 3 - Docs
history:
- at: '2026-10-30T23:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/recovery/troubleshoot-merge.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Changelog and recovery docs for the cleared record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`). Address every item, then record what changed with
  `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

Tell the operator what a clean rollback now leaves, in the two places they look:

- an `[Unreleased]` changelog entry with the `(#6770)` reference, impact-first, under 1,200
  characters;
- a subsection in the recovery how-to stating that a failed run which rolled back completely
  leaves no record, that the next run's reconciliation window starts at the target's current
  tip, and that a plain `--abort` is then a no-op.

Acceptance: SC-001, SC-002, SC-003 documented; docs freshness check green.

## Context & Constraints

Read first:

- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/spec.md` (what a user gets).
- `docs/changelog/CHANGELOG.md` — the `[Unreleased]` section's existing entry style (bold
  impact-first lead, `(#NNNN)`, **Before:** / **After:**).
- `docs/guides/how-to/recovery/troubleshoot-merge.md` — its voice is "what you see / what it
  means / what to run"; the existing sections on `--abort` and on a branch that cannot be
  restored are the neighbours you must stay consistent with.

Constraints:

- `CHANGELOG.md` at the repo root is a symlink to `docs/changelog/CHANGELOG.md`: edit the real
  file under `docs/`.
- Audience: the external project owner who just hit the failure (frontmatter already names it).
- No version numbers, no internal symbol names, no machine-local paths.

## Branch Strategy

- **Strategy**: single_branch on `issue-6770-consolidate-rerun-fresh-baseline`
- **Planning base branch**: `issue-6770-consolidate-rerun-fresh-baseline`
- **Merge target branch**: `issue-6770-consolidate-rerun-fresh-baseline`

## Subtasks & Detailed Guidance

### Subtask T001 – The changelog entry

- **Steps**: add one `[Unreleased]` bullet in `docs/changelog/CHANGELOG.md`, in the file's
  existing style:
  - bold, impact-first lead naming the recovery path that now works, with `(#6770)`;
  - **Before:** the re-run inherited the first attempt's target tip, re-flagged commits that had
    landed since, rolled the target back over them, and a plain `--abort` then refused;
  - **After:** a rollback that restored everything clears the record, so the next run starts
    from the target's current tip and a plain `--abort` simply reports that nothing is active;
    a partial rollback still keeps the record.
  - Reference the closed #5667 recurrence and keep under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Notes**: no headings inside the bullet; match the surrounding entries' tense.

### Subtask T002 – The recovery how-to subsection

- **Steps**: in `docs/guides/how-to/recovery/troubleshoot-merge.md`, add a short subsection (use
  the nearest existing anchor and heading level) under the undo/abort material, e.g.
  "### A failed run that rolled back completely leaves no record". State:
  - what you see: the rollback report ends with every branch `restored`/`unchanged`, and the run
    says the consolidation record was cleared;
  - what it means: nothing of that attempt is on the target, so there is nothing to resume;
  - what to run: fix the cause, then a plain `spec-kitty consolidate --mission <slug>` — its
    reconciliation considers only what is new since the target's current tip; a plain
    `--abort` is a no-op that reports `No active merge state`;
  - the boundary: a rollback that leaves a branch `NOT restored` keeps the record, and that is
    where `--release-branch` applies (link the existing section).
  - Bump the page's `updated:` frontmatter date to the commit date.
- **Files**: `docs/guides/how-to/recovery/troubleshoot-merge.md`.
- **Notes**: keep it to roughly 10–14 lines; do not restate the whole rollback contract.

### Subtask T003 – Freshness check

- **Steps**: run `uv run python -m scripts.docs.check_docs_freshness --ci` and record the result
  (expect errors=0) in the WP history. Do not rebuild the whole CLI reference: this diff changes
  no command surface.
- **Notes**: if the check reports an unrelated pre-existing error, record it verbatim and flag it
  in the PR's `## Deferred` instead of regenerating unrelated pages.

## Test Strategy

No code tests. The doc gates are the freshness check above (and CI's docs jobs).

## Risks & Mitigations

- Over-claiming: the entry must not say a failed run "never needs `--abort`" — a partial rollback
  still does.
- Symlink discipline: edit `docs/changelog/CHANGELOG.md`, never the root symlink target twice.

## Review Guidance

- Does the entry lead with the user-visible outcome, cite `(#6770)`, and fit under 1,200 chars?
- Is the how-to consistent with the new operator line in `executor._report_rollback`?
- Is the partial-rollback boundary stated, so nobody reads the change as "errors never leave
  state"?

## Progress & Status

Use `spec-kitty agent tasks add-history WP03 --note "..."` and
`spec-kitty agent tasks move-task WP03 --to <status>`.
