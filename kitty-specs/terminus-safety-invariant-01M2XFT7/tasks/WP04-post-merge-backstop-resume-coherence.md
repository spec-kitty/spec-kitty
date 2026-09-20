---
work_package_id: WP04
title: Post-merge backstop resume-coherence
dependencies:
- WP02
requirement_refs:
- FR-008
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/done_bookkeeping.py
create_intent:
- tests/merge/test_done_bookkeeping_rollback_coherence.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/done_bookkeeping.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, implementer-only boundaries, and TDD/type-safety discipline. Do not proceed until the profile is loaded.

## Objective

Make the post-merge backstop in `done_bookkeeping.py` cooperate with WP02's rollback so that after a post-mutation failure resets the coordination ref/worktree, the committed coordination `done` markers (`_durable_done_wps_on_coordination_ref`) stay coherent with the worktree bytes — a later `--resume` reads a consistent state with no split-brain. Delivers **FR-008** (the defense-in-depth half of the rollback, alongside WP02).

## Context

- **Spec**: FR-008 (resume-coherent rollback); US3-1 (a rolled-back merge leaves committed coordination `done` markers and worktree state mutually coherent, so a later `--resume` reads a consistent state); NFR-001 (zero manual git-surgery to continue).
- **Contract**: `contracts/terminus-safety-contract.md` → **C-ROLLBACK**: after a completion command mutates and a later step fails, coord ref/worktree reset to the checkpoint; `--resume` reads a coherent state (committed `done` markers ↔ worktree bytes consistent).
- **Data model**: `data-model.md` → coordination checkpoint; reset semantics reference `_durable_done_wps_on_coordination_ref` (`done_bookkeeping.py:595`); the rollback runs BEFORE `_phase_cleanup_worktrees_and_branches` (executor :1588).
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/merge/done_bookkeeping.py:444` — `_assert_merged_wps_reached_done` (the post-merge backstop assertion)
  - `src/specify_cli/merge/done_bookkeeping.py:595` — `_durable_done_wps_on_coordination_ref` (reads committed `done` markers off the coord ref)
  - `src/specify_cli/merge/done_bookkeeping.py:663-674` — the transactional-done consumer that reads `durable_done`
  - `src/specify_cli/merge/done_bookkeeping.py:743` — `_assert_merged_wps_reached_done(main_repo, mission_slug, all_wp_ids)` (driven from the run)
  - WP02's checkpoint/reset primitive in `executor.py` (the coord ref/worktree reset this WP must stay coherent with)

## Per-Subtask Guidance

### T013 — RED-first resume-coherence test

Create `tests/merge/test_done_bookkeeping_rollback_coherence.py`, `@pytest.mark.regression`. Simulate a merge that consolidated + marked `done` markers on the coordination ref, then a post-mutation failure that triggers WP02's reset. Assert a subsequent `--resume` reads a coherent state: the committed coordination `done` markers agree with the worktree bytes — NO split-brain (a `done` marker with no corresponding worktree content, or vice versa). RED before T014, GREEN after.

### T014 — Backstop cooperates with WP02's rollback

Ensure the post-merge validation-failure path and the durable-done reader (`_durable_done_wps_on_coordination_ref`) observe the post-reset state consistently. Concretely: after WP02 resets the coord ref/worktree on a post-mutation failure, `_durable_done_wps_on_coordination_ref` and `_assert_merged_wps_reached_done` must not leave `done` markers that disagree with the reset worktree. Coordinate through WP02's shared checkpoint primitive (do NOT introduce a second, independent read/reset path — C-001). Verify the ordering: the reset precedes the point where the durable-done reader would otherwise persist/observe stale markers.

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. PR to `main` opens later; the operator merges.
- This WP depends on WP02's checkpoint/reset primitive — land after WP02.
- Commit the T013 red-first test as a distinct commit before T014.

## ATDD / Test Strategy (red-first defect)

- **Resume-coherence** `@pytest.mark.regression` (T013): a resume after a rolled-back merge reads coherent state; RED before the fix (split-brain observable), GREEN after.
- Run the full `tests/merge/` directory plus any resume/backstop tests. Record commands + counts. Because this WP depends on WP02, verify against the branch state that includes WP02.

## Definition of Done

- [ ] After a rolled-back merge, committed coordination `done` markers stay coherent with worktree bytes; `--resume` reads a consistent state (FR-008).
- [ ] No second/independent reset or read path introduced — cooperation is through WP02's shared checkpoint primitive (C-001).
- [ ] T013 regression test green; full `tests/merge/` green.
- [ ] `ruff` + `ruff format --check` + `mypy` clean; C901 ≤ 15.
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Ordering seam with WP02** — if the durable-done reader observes markers before the reset, split-brain persists. Mitigation: verify reset-before-read ordering; test the exact resume path.
- **Duplicate reset path** — accidentally adding a second rollback mechanism here. Mitigation: consume WP02's primitive; do not fork it.
- **Dependency drift** — WP04 lands after WP02; running against a pre-WP02 branch masks the coherence bug. Mitigation: verify on the integrated branch.

## Reviewer Guidance (reviewer-renata)

- Confirm FR-008 coherence: committed `done` markers ↔ worktree bytes after a reset; `--resume` consistent.
- Confirm no forked reset/read path — WP04 rides WP02's checkpoint primitive (C-001).
- Confirm the reset-before-read ordering is correct and tested.
- Confirm the resume-coherence test is genuinely red-first (split-brain observable before the fix).
