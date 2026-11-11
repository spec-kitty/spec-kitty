---
work_package_id: WP04
title: The next consolidate rematerializes the coordination worktree (#5406)
dependencies: []
requirement_refs:
- FR-007
- FR-008
- SC-003
planning_base_branch: fix/7544-coord-closeout-recovery
merge_target_branch: fix/7544-coord-closeout-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7544-coord-closeout-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7544-coord-closeout-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-recovery-01M75QCY
base_commit: 80c657e2ac6de6080a409143450df9e847dae6c3
created_at: '2026-11-11T16:45:16.098317+00:00'
subtasks:
- T012
- T013
- T014
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/integration/test_consolidate_after_abort_5406.py
- tests/consolidation/test_missing_lanes_remedy_topology_5406.py
- docs/changelog/unreleased/5406-consolidate-after-abort.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/entry_preflight.py
- tests/integration/test_consolidate_after_abort_5406.py
- tests/consolidation/test_missing_lanes_remedy_topology_5406.py
- docs/changelog/unreleased/5406-consolidate-after-abort.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 - The next consolidate rematerializes the coordination worktree (#5406)

## Goal

After `consolidate --abort` tore down the coordination worktree (kept by the 2026-09-30 ruling), the
next `consolidate` rematerializes it on demand through `materialize_coord_surface_for_write` and
proceeds. A missing lanes manifest names a remedy that works for the Mission's stored topology: the
`git checkout <branch>` remedy stays only for a `single_branch` holder.

Root cause: `research/code-grounding.md` section 2.4. Design: `plan.md` IC-04.

## Subtasks

- **T012** RED (CLI): fixture, `consolidate` with `WP20_FAIL_BEFORE=_phase_reconcile_before_teardown`
  (`WP20_FAIL_KIND=exit`), then `consolidate --abort`, then `consolidate`: the last run exits 0 and
  the target carries every lane's file. Red on the base with the "lanes.json is not on the current
  checkout ... git checkout" refusal. p0_repro marker while red.
- **T013** Fix: before `run_lane_based_consolidation` resolves the status dir, when the seam's
  `PRIMARY_METADATA` dir has no `meta.json`, locate the branch holding `kitty-specs/<slug>/meta.json`
  (`branch_holding_path`), read it from that branch, and when its stored topology is a coordination
  topology whose `coordination_branch` is that branch, call
  `materialize_coord_surface_for_write(main_repo, slug, coordination_branch=..., mid8=resolve_declared_mid8(meta, slug))`,
  then rebuild the seam. Keep it a small helper in `entry_preflight.py`; the executor only calls it.
- **T014** `_require_lanes_json_naming_mission_branch`: coordination-topology holder -> remedy says
  the coordination worktree is rematerialized from the local branch and names what to do when that
  branch is not local (fetch it, then re-run `consolidate`); single_branch holder -> unchanged text
  (control test). Unit tests in `tests/consolidation/`. Changelog fragment.

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
