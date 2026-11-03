---
work_package_id: WP01
title: Defer a non-artifact coordination residual in accept
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7091-accept-coord-residual-artifact-commit
merge_target_branch: issue-7091-accept-coord-residual-artifact-commit
branch_strategy: Planning artifacts for this mission were generated on issue-7091-accept-coord-residual-artifact-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7091-accept-coord-residual-artifact-commit unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-7091-accept-coord-residual-artifact-commit-01M6G9GS
base_commit: 63406c8ce3fac2b0baef2c39c15fe0df14589c00
created_at: '2026-11-03T09:14:35.987484+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Classification
history:
- at: '2026-11-03T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/accept.py
- tests/specify_cli/cli/commands/test_accept_residual_partition.py
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Defer a non-artifact coordination residual in accept

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

- `accept.py::_run_residual_acceptance_commit` excludes a coordination-leg residual path whose
  `kind_for_mission_file` verdict is `None` (the keep-local mission-root
  `mission-events.jsonl`, #5669) from the commit batch, so a ready coordination-topology
  mission no longer exits 1 on `safe_commit: refusing to stage path under .worktrees/`.
- `_note_deferred_residuals` reports every deferred path on the acceptance result (text and
  `--json` lanes) with the #5669 rationale; an empty deferral adds no note.
- Classified dirt keeps its verdicts: a COORD artifact in the same run still commits on the
  coordination branch, and a PRIMARY-classified artifact stranded in the coordination worktree
  still routes PRIMARY and still refuses loudly.
- No classifier, partition, churn-owner, readiness or gate change: the pinned #5669 C-002 guard
  (`is_self_bookkeeping_churn` / `is_toolchain_generated_churn` false for the log) stays green
  untouched, and `is_status_state_path` stays narrow.
- A flat/single-branch mission still commits its dirty `mission-events.jsonl` on its own branch.

Success: FR-001 … FR-007; NFR-001 … NFR-003; C-001 … C-003; SC-001 … SC-004.

## Context & Constraints

- Read `kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/spec.md`, `plan.md`
  (DD-01..DD-05) and `contracts/accept-residual-routing.contract.md` first.
- Review cycle 1 rejected classifying the log as a COORD kind: that reverses #5669's keep-local
  ruling, flips `is_coord_residue_churn`, and fails
  `tests/review/test_mission_events_dirty_survivor_5669.py::test_global_churn_owner_still_treats_mission_events_as_real_dirt`.
  Do not re-introduce it.
- Reproduction on current `main` (confirmed during grounding): a real coordination-topology
  fixture with a dirty coord-worktree `mission-events.jsonl` makes
  `_run_residual_acceptance_commit` raise `ResidualCommitError` naming
  `safe_commit: refusing to stage path under .worktrees/`.
- Do not touch `src/mission_runtime/artifacts.py`,
  `src/specify_cli/coordination/commit_router.py`, `src/specify_cli/git/**`, the readiness
  pipeline, or `tests/review/test_mission_events_dirty_survivor_5669.py`. Do not add a marker,
  skip or xfail.
- Changelog is a per-PR fragment under `docs/changelog/unreleased/` (see
  `docs/changelog/unreleased/README.md`), never an edit to `docs/changelog/CHANGELOG.md`.

## Subtasks

- **T001 (red-first)** Add the survivor regression test to
  `tests/specify_cli/cli/commands/test_accept_residual_partition.py`, reusing the module's real
  `_build_coord_mission` fixture: commit a baseline `mission-events.jsonl` on the coordination
  branch, rewrite it in the coordination worktree, also dirty the matrix, then call
  `_run_residual_acceptance_commit`. Assert no exception, the matrix commits on the coordination
  branch, the primary branch head is unchanged, the log is NOT in the coordination branch's HEAD
  and is still tracked-modified in the worktree. Run it first: it must fail with the
  `safe_commit` refusal.
- **T002** Add `_nonartifact_residual_paths(paths)` (pure, classifier-derived via
  `kind_for_mission_file`) and subtract its result from `coord_dirty` in
  `_run_residual_acceptance_commit`, with a docstring explaining the #5669 boundary and why the
  router/`safe_commit` must not see these paths.
- **T003** Add `_note_deferred_residuals(run, outcome)` and call it at the end of
  `_run_post_acceptance_steps`; it appends one `AcceptanceResult.notes` entry naming the
  deferred paths; its own failures must never become a new failure path
  (`# noqa: BLE001` with the advisory rationale). Add a paired unit test for the note and the
  empty-deferral control.
- **T004** Add the narrowness test: dirty `spec.md` in the coordination worktree still raises
  through `_run_residual_acceptance_commit` with `refusing to stage path under .worktrees/`.
- **T005** Add the flat/single-branch control test: dirty `mission-events.jsonl`, no
  `coordination_branch`, unprotected working branch — the residual commit still lands it on
  that branch and the tree is clean.
- **T006** Run the targeted modules and the linters, then record the self-review:
  `tests/specify_cli/cli/commands/test_accept_residual_partition.py`,
  `tests/review/test_mission_events_dirty_survivor_5669.py`,
  `tests/specify_cli/cli/commands/test_accept_clean_tree.py`,
  `tests/specify_cli/cli/commands/test_accept_decomposition.py`,
  `tests/integration/test_accept_matrix_coord_partition.py`,
  `tests/mission_runtime/test_artifact_partition_mapping.py`,
  `tests/architectural/test_write_surface_placement_guard.py`; plus `ruff check`,
  `ruff format --check` and `mypy` on the touched files. Do NOT run a full heavy suite.
- **T007** Add the changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` after the PR
  number exists, following `docs/changelog/unreleased/README.md`.

## Definition of Done

- The survivor test failed before T002 and passes after it (paste both results in the PR's
  `Tests run`).
- `git diff` touches only `accept.py`, the accept residual test module and the changelog
  fragment.
- No gate, marker, skip, xfail, classifier entry or churn-owner predicate is changed.

## Risks

- Deferring *every* unclassified coordination residual is intentional (not a filename literal):
  the note keeps it visible, and misscoped unclassified agent artifacts are a recorded
  follow-up.
- A mocked coordination root cannot reproduce the `safe_commit` refusal — use the real
  worktree fixture.
- The note's extra `git status` must stay advisory; it may not add a failure path to accept.
