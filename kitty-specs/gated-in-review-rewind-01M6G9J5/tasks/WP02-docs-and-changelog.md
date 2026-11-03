---
work_package_id: WP02
title: The operator-facing position
dependencies:
- WP01
requirement_refs:
- FR-008
- SC-001
- C-003
- C-005
planning_base_branch: issue-7080-gated-in-review-rewind
merge_target_branch: issue-7080-gated-in-review-rewind
branch_strategy: Planning artifacts for this mission were generated on issue-7080-gated-in-review-rewind. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7080-gated-in-review-rewind unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - The position
history:
- at: '2026-11-03T09:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/status-model.md
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/architecture/status-model.md
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7080'
---
# Work Package Prompt: WP02 – The operator-facing position

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Context

WP01 changed the writer's verdicts and the emit path's recorded pointer. The status reference
(`docs/architecture/status-model.md`, "Forced rewinds out of review") is the operator-facing
statement of that rule and is currently written for a one-edge world.

## Subtasks

**T008.** Update `docs/architecture/status-model.md`: name the contract's three gated rewinds
(`for_review`, `in_review`, `approved` -> `in_progress`), state that the local set holds the
edges this tree gates (on this branch: `for_review` and `in_review`; `approved` is #6955 / PR
#7102), state that the requirement holds whether or not the event is forced, add the new guard
row for `in_review -> in_progress`, add the emit-path row to the writer-to-pointer table (a
structured review result's `reference` is recorded when no `--review-ref` was supplied; an
explicit pointer wins), and keep the append-only position honest for rows written before this
fix. Keep every statement true for this branch — do not claim the `approved` edge is locally
gated here.

**T009.** Add the per-PR changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` (the PR
number once the PR exists), following `docs/changelog/unreleased/README.md`: bold impact-first
lead with `(#7080)`, before/after, under 1,200 characters. Never edit
`docs/changelog/CHANGELOG.md`.

**T010.** Run the docs gates: `uv run python -m scripts.docs.check_docs_freshness --ci`
(expect errors=0) and the terminology guard
(`uv run pytest -q tests/architectural/test_no_legacy_terminology.py`), plus markdownlint on
the touched page if the fast gate covers it. Regenerate nothing this diff does not change.

## Definition of Done

- The reference page describes the edge set this branch actually has, with the derivation path
  and the recovery position.
- The changelog fragment lints and states the before/after.
- `check_docs_freshness --ci` reports errors=0.
