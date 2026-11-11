---
work_package_id: WP05
title: End-to-end coordination closeout with no hand-run git (#7544 Done-when)
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-009
- SC-001
- SC-002
planning_base_branch: fix/7544-coord-closeout-recovery
merge_target_branch: fix/7544-coord-closeout-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7544-coord-closeout-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7544-coord-closeout-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-recovery-01M75QCY
base_commit: 6c0fe98e0df3d1795854a30cab38b8b0d5a21b14
created_at: '2026-11-11T18:13:13.169360+00:00'
subtasks:
- T015
- T016
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: tests/integration/test_coord_closeout_recovery_7544.py
create_intent:
- tests/integration/test_coord_closeout_recovery_7544.py
execution_mode: code_change
owned_files:
- tests/integration/test_coord_closeout_recovery_7544.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 - End-to-end coordination closeout with no hand-run git (#7544 Done-when)

## Goal

One integration module pins the #7544 Done-when through the CLI.

## Subtasks

- **T015** `test_closeout_accept_fail_abort_rerun`: a 6-WP default Mission (settled
  `lanes_with_coord`) -> record verdicts -> `accept` (exit 0) -> `consolidate` with an injected
  late-phase failure (exit 1, rollback restores every branch, coordination checkout clean) ->
  `consolidate --abort` (exit 0) -> `consolidate` (exit 0); the target carries every lane's file.
  No hand-run git after the fixture build.
- **T016** `test_closeout_after_kill_in_done_commits`: same fixture state, `consolidate` killed at the
  WP02 done commit -> `consolidate --abort` (exit 0, nothing "moved by another actor") ->
  `consolidate` (exit 0), every lane landed.

Build the fixture once per module and copy it per test (`shutil.copytree` keeps worktree `.git`
files pointing at absolute paths, so build into the final location or rebuild per test if copying
breaks worktrees). Mark `slow`; timeout 1200 s.

## Doctrine (binding)

- Load your profile first (`/spk-charter-profile-load`), then `spec-kitty charter context --action implement`.
- Standing Order 4 / test-first-bug-fixing: commit the RED test (through the CLI entry point named below) as its own commit BEFORE the fix. While red it carries `@pytest.mark.p0_repro(issue=7544)`; the fix commit removes the marker.
- Tidy-first: any behaviour-preserving extraction you need goes in a commit before the red test.
- Never: a second rollback/restore path, weaker CAS, foreign edits treated as residue, new size/ratchet gates.
- Quality: ruff check, `ruff format --check --force-exclude <files>`, mypy clean, complexity <= 15.
- Changelog: one fragment in `docs/changelog/unreleased/` (see its README), `fixed` section.
- Commit trailer on every commit: `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.
- Append any tooling friction to `traces/tooling-friction.md` (coordination worktree).

## Fixture

Reuse `build()` / `cli()` / `consolidate()` from `tests/integration/test_default_mission_consolidate_lands_primary.py`
(a default Mission with 3 code WPs settled to `lanes_with_coord`, root checkout and target on the
unprotected branch `work`, every WP approved; its shim injects `WP20_FAIL_BEFORE=<executor phase>`).
Import them; do not copy them. Mark the test module `integration`, `git_repo`, `non_sandbox`, `slow`.
