---
work_package_id: WP02
title: Residue context reads the stored topology where the Mission's metadata lives (#7540 item 2)
dependencies: []
requirement_refs:
- FR-004
- FR-005
planning_base_branch: fix/7544-coord-closeout-recovery
merge_target_branch: fix/7544-coord-closeout-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7544-coord-closeout-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7544-coord-closeout-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-recovery-01M75QCY
base_commit: 19fae4b4ee73df1afab9ffed7166b9f21a2a5edb
created_at: '2026-11-11T16:43:33.870403+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/coherence.py
create_intent:
- tests/coordination/test_residue_context_settled_topology_7540.py
- tests/integration/test_rollback_coord_residue_7540.py
- docs/changelog/unreleased/7540-rollback-coord-residue.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/coordination/coherence.py
- tests/coordination/test_residue_context_settled_topology_7540.py
- tests/integration/test_rollback_coord_residue_7540.py
- docs/changelog/unreleased/7540-rollback-coord-residue.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 - Residue context reads the stored topology where the Mission's metadata lives (#7540 item 2)

## Goal

`ResidueContext.for_mission` reads the Mission's stored topology from the directory the placement
seam resolves for `PRIMARY_METADATA` (`mission_runtime.placement_seam(repo_root, slug).read_dir(...)`),
falling back to today's raw `repo_root/kitty-specs/<slug>` join only when the seam cannot resolve.
A settled default Mission (whose `meta.json` exists only on the Mission branch, held by the
coordination worktree) then gets its real residue rules, so the single rollback authority can resync
its own status log/snapshot in the coordination checkout instead of refusing.

Root cause: `research/code-grounding.md` section 2.2. Design: `plan.md` IC-02.

## Subtasks

- **T005** RED (CLI): on the fixture, run `consolidate` with an injected failure placed after the
  done commits while the coordination worktree holds this run's own uncommitted status log line
  (e.g. `WP20_FAIL_BEFORE=_phase_capture_and_baseline` plus a test-side appended status line
  written by the shim's pre-hook, or the WP02-specific hook you add to your own test shim);
  assert the rollback restores the coordination branch and the coordination checkout is clean
  (no "uncommitted local changes" note). Negative control in the same file: a non-status edit
  (e.g. a new `notes.md` under the Mission dir) in the coordination worktree still refuses the
  resync and is preserved. p0_repro marker while red.
- **T006** Fix `for_mission` (and keep `residue_context_or_strictest` semantics: absent everywhere
  -> strictest). Unit tests in `tests/coordination/`: root without `meta.json` + coordination
  worktree with it -> stored topology; seam failure -> raw join; absent everywhere ->
  FileNotFoundError as today.
- **T007** Re-run every `for_mission` caller's tests (rollback, workspace teardown, lane allocator,
  auto-rebase, bake) and the placement gates (`tests/architectural/test_no_write_side_rederivation.py`,
  `test_no_read_side_bypass.py`, `test_single_mission_surface_resolver.py`). If a ledger lists the
  raw join, re-point it, never loosen. Changelog fragment.

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
