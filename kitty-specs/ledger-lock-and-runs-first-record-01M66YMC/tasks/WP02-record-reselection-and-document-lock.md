---
work_package_id: WP02
title: Record the reselection, document the lock
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
- C-004
- C-005
- SC-003
- SC-004
planning_base_branch: issue-6613-ledger-lock-and-runs-first-record
merge_target_branch: issue-6613-ledger-lock-and-runs-first-record
branch_strategy: Planning artifacts for this mission were generated on issue-6613-ledger-lock-and-runs-first-record. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6613-ledger-lock-and-runs-first-record unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ledger-lock-and-runs-first-record-01M66YMC
base_commit: 9505ad35e8c531a72a41b90360bec2834348df7d
created_at: '2026-10-30T19:44:00.762357+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - The record
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/
create_intent:
- tests/docs/test_migration_ledger_adr_records_reselection.py
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- docs/development/reference/events-in-core.md
- docs/changelog/CHANGELOG.md
- tests/docs/test_migration_ledger_adr_records_reselection.py
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Record the reselection, document the lock

## ⚡ Do This First: Load Agent Profile

Load `scribe-sally` (`spec-kitty agent profile show scribe-sally`) and behave according to its
guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`) for feedback and address every
item before marking the work done.

---

## Objectives & Success Criteria

The second half of #6613: ADR `2026-10-17-1` says selection is ledger-diff **plus** the `runs_first`
structural reselection, which is what the code has always done and the ADR never recorded. The
developer reference's state-ledger rule gains both facts (the new append lock and the reselection),
and a doc guard keeps the record true. A user-facing changelog entry is added.

Done means:

- `tests/docs/test_migration_ledger_adr_records_reselection.py` fails on `main` and passes after the
  edits (SC-003, SC-004).
- The ADR amendment is factual and names `structural_detect`, `reselect_when_recorded`, the
  single-`runs_first` guard and the `detect()`-as-idempotency-guard boundary.
- `detect()`/reselection behaviour is unchanged, and the existing
  `tests/upgrade/test_registry_runs_first.py` still pins it (FR-007).
- Docs gates are clean: `check_docs_freshness --ci` reports `errors=0`, ADR frontmatter is valid,
  and `tests/architectural/test_events_import_frozen.py` passes (the frozen page is untouched).

## Context & Constraints

- **C-004**: recording is not deciding. Do not remove, widen or narrow the reselection; the issue
  leaves removal to an operator.
- **C-005 / freeze**: `docs/architecture/event-ledger-writers-and-readers.md` is pinned by
  `tests/architectural/test_events_import_frozen.py` (blob `c2943d49…`, ADR 2026-10-29-1 D-9).
  **Do not edit it.** Its G-15 closure and writer-row correction are deferred to the PR's
  `## Deferred`.
- "Ledger" in this mission is the *migration state ledger*; say so, so no reader confuses it with
  the event ledger.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-6613-ledger-lock-and-runs-first-record`; completed changes must merge back into `issue-6613-ledger-lock-and-runs-first-record`.
- **Planning base branch**: `issue-6613-ledger-lock-and-runs-first-record`
- **Merge target branch**: `issue-6613-ledger-lock-and-runs-first-record`

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first doc guard

- **Purpose**: Make the documentation claim falsifiable.
- **Steps**: Create `tests/docs/test_migration_ledger_adr_records_reselection.py` (mark it
  `pytest.mark.unit`). Read the ADR and the developer reference as text and assert:
  1. the ADR contains `structural_detect` and `reselect_when_recorded`;
  2. the ADR states the recorded-but-structurally-present case (look for the wording that a
     recorded `runs_first` migration is re-selected when the predicate fires);
  3. the ADR states at most one migration may set `runs_first`;
  4. `events-in-core.md`'s state-ledger rule names the ledger's lock.
  Add the same-fixture positive control: the guard reads the real files (no fixtures), so also assert
  the page/ADR file exists and is non-empty — a missing file must fail loudly, not silently pass.
- **Files**: `tests/docs/test_migration_ledger_adr_records_reselection.py`
- **Parallel?**: Yes.
- **Notes**: Run it before the doc edits and capture the red output in the WP history.

### Subtask T007 – ADR amendment

- **Purpose**: Record the behaviour in the architecture authority.
- **Steps**: Append `## Amendment 2026-10-30 (#6613: the runs_first structural reselection, and the
  ledger lock)` after the last existing amendment in
  `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`. Content:
  - The §1 sentence "collapses to 'is this id in the applicable ledger'" is superseded in part: for a
    `runs_first` migration, `reselect_when_recorded` still re-selects when `structural_detect`
    reports the old state present (a pulled `metadata.yaml` or a merge can revive legacy state).
  - `detect()` remains the pre-`apply()` idempotency guard, never the skip authority.
  - At most one registered migration may set `runs_first` (`registry.py`).
  - Selection is therefore: ledger-diff for every migration, plus reselection for the single
    `runs_first` migration whose structural predicate fires.
  - The §1 "single-writer, lock deliberately not built" paragraph is superseded: the append now
    holds a dedicated sidecar lock via `kernel.locks.machine_file_lock`, bounded wait, and the
    per-partition sidecar path rule (so no anchored-lock-path helper is added; #6727 owns that).
  - State plainly that removing the reselection remains an open operator decision — this amendment
    records, it does not decide.
- **Files**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
- **Parallel?**: Yes.
- **Notes**: Keep the file's existing frontmatter untouched (status stays `accepted`); an amendment
  section is the established shape in this ADR (see its four existing amendments).

### Subtask T008 – Developer reference rule

- **Purpose**: The live reference a contributor reads must not contradict the code.
- **Steps**: In `docs/development/reference/events-in-core.md`, extend the "Call the state files by
  their names" bullet (or add one directly after it) with: the migration ledger's append takes a
  dedicated per-partition sidecar lock (bounded wait; never the payload file), and a recorded
  `runs_first` migration is re-selected when its `structural_detect` fires.
- **Files**: `docs/development/reference/events-in-core.md`
- **Parallel?**: Yes.

### Subtask T009 – Changelog entry

- **Purpose**: User-facing change recorded the repo's way.
- **Steps**: Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a
  symlink to it): bold impact-first lead with `(#6613)`, then before/after, under 1,200 characters.
  Match the surrounding entry shape.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: No — after T007/T008 settle the wording.

### Subtask T010 – Docs gates

- **Steps**:
  ```
  uv run python -m scripts.docs.docs_index --write
  uv run python -m scripts.docs.freshen_adr_inventory
  uv run python -m scripts.docs.check_docs_freshness --ci      # expect errors=0
  uv run pytest tests/architectural/test_events_import_frozen.py -q
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  uv run pytest tests/docs -q
  ```
  Commit any regenerated artifacts (index/inventory) with the doc change.
- **Files**: n/a
- **Parallel?**: No.

## Test Strategy

- The doc guard is the acceptance test for this WP; it must be red first. A guard that only greps
  for a word is weak, so it asserts the *substance* (the recorded-but-structural case, the
  single-`runs_first` guard, the lock sentence), not just token presence.
- Behaviour stays pinned by the pre-existing `tests/upgrade/test_registry_runs_first.py` and
  `tests/upgrade/test_clone_local_selection.py`; run both and report them green.
- No compiler/typecheck surface changes in this WP (docs + a markdown-reading test module); still
  run `uv run --extra lint mypy tests/docs/test_migration_ledger_adr_records_reselection.py`.

## Risks & Mitigations

- **Amendment reads as a decision** → phrase it as a record, and name the open operator question.
- **Frozen page edited by reflex** → the guard/gate runs in T010; if it fails, revert the page edit
  and move the row correction to `## Deferred`.
- **Docs freshness drift** → regenerate index/inventory in the same commit.

## Review Guidance

- Verify the amendment's claims against `base.py` (`reselect_when_recorded`, `structural_detect`,
  `runs_first` docstring) and `registry.py`'s one-`runs_first` guard — every sentence must be
  checkable in code.
- Verify the frozen page has no diff.
- Verify the changelog entry is under 1,200 characters and leads with impact.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
