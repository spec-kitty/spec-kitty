---
work_package_id: WP02
title: The operator-facing position
dependencies:
- WP01
requirement_refs:
- FR-007
- SC-001
- C-003
- C-005
planning_base_branch: issue-6955-wire-valid-approved-reopen
merge_target_branch: issue-6955-wire-valid-approved-reopen
branch_strategy: Planning artifacts for this mission were generated on issue-6955-wire-valid-approved-reopen. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6955-wire-valid-approved-reopen unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-wire-valid-approved-reopen-01M6EJW0
base_commit: 5265ed1afef4bd5c223fecff12208b351e042516
created_at: '2026-11-02T20:37:08.868270+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 2 - The position
history:
- at: '2026-11-02T17:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/status-model.md
create_intent:
- tests/status/test_status_model_reference.py
execution_mode: code_change
model: ''
owned_files:
- docs/architecture/status-model.md
- docs/changelog/unreleased/
- tests/status/test_status_model_reference.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6955'
---
# Work Package Prompt: WP02 – The operator-facing position

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address every item; record with
`spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Make the change legible to the operator who hits it: the status reference states the gated
family, the pointer each writer supplies, and — honestly — what may be done about rows
written before the fix. Ship the change as a per-PR changelog fragment, not a
`CHANGELOG.md` edit.

Done when:

1. `docs/architecture/status-model.md` names the three-edge family as force-insurmountable,
   keeps the writer→pointer table complete (including the sentinel and `agent action
   implement`), states that the local edge set equals the pinned contract's family, and
   states the append-only, no-rewrite position for pre-fix rows plus the `migration:` audit
   carve-out;
2. `docs/changelog/unreleased/<pr>.fixed.md` exists in the shape
   `docs/changelog/unreleased/README.md` requires;
3. `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and the
   reference's new statements are pinned by a test.

## Context & Constraints

- Spec FR-007, SC-001, C-003, C-005. Plan §"Implementation Concern Map" IC-04. Research R5,
  R6. Data model §`REVIEW_REF_REQUIRED_EDGES`.
- **No `[Unreleased]` edit.** `check_changelog_style` rejects the old shape since #6988; use
  the fragment directory and read its README first (`C-005`).
- **Do not invent a repair.** The tool ships no migration for legacy rows; the doc says the
  only supported correction is an appending migration authored by a maintainer (`C-003`).
- **Do not regenerate the whole CLI reference.** Only regenerate the docs surface this diff
  changes; the shared machine asset cache is written by other agents concurrently.
- Keep the existing `#6514` text intact where it is still true; extend it for the family
  rather than rewriting the section.

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`

Implement with `spec-kitty agent action implement WP02 --agent pi --mission wire-valid-approved-reopen-01M6EJW0`.

## Subtasks & Detailed Guidance

### T007 – Extend the status-model reference (own commit)

In `docs/architecture/status-model.md`:

- §"Force override" and the guard table: the force-insurmountable requirement now covers the
  whole gated family (`for_review`/`in_review`/`approved -> in_progress`), not one edge.
- §"Forced rewinds out of review": extend the writer table with the approved reopen (the
  `move-task` forced arm now records `force-override` when no feedback file is supplied) and
  state that a supplied `--review-feedback-file` still wins (the #6845 arm).
- Replace the sentence that says the edge set is "deliberately narrow: only
  `for_review -> in_progress`" with the current truth: the set equals the pinned contract's
  gated family, and both the writer and the auditor read that one definition. Cite #6955.
- §"Rows written before this refusal": keep the position, note that it now covers the whole
  family (legacy `approved`/`in_review` pointerless rows), and keep the `migration:` carve-out
  sentence accurate.

Commit: `docs(6955): state the gated rewind family and its recovery position`.

### T008 – Changelog fragment (own commit)

Read `docs/changelog/unreleased/README.md`, then add
`docs/changelog/unreleased/<pr>.fixed.md` (rename to the real PR number once the PR exists —
the wrap-up step owns that rename). Impact-first lead, the `(#6955)` reference, before and
after, under 1,200 characters, matching the fragment schema exactly.

Commit: `docs(6955): add the changelog fragment`.

### T009 – Gates and the reference pin (own commit)

- Add `tests/status/test_status_model_reference.py`: assert the page names the three family
  edges, the `force-override` sentinel, and the append-only position (grep-level assertions
  so a future edit cannot silently drop them).
- Run `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0) and
  `uv run pytest -q tests/architectural/test_no_legacy_terminology.py`.
- Run the changelog style gate CI uses (find it under `scripts/` and run it against the new
  fragment) so the fragment shape is proven before the PR exists.

Commit: `test(6955): pin the reference's gated-family statements`.

## Test commands

```bash
uv run pytest -q tests/status/test_status_model_reference.py
uv run pytest -q tests/architectural/test_no_legacy_terminology.py
uv run python -m scripts.docs.check_docs_freshness --ci
```

## Definition of Done

- The reference is accurate against the merged behaviour of WP01 (read the final code, do not
  trust this prompt).
- The fragment validates under the repository's changelog style gate.
- Docs freshness errors=0; the reference pin test fails if the family statement is removed.
