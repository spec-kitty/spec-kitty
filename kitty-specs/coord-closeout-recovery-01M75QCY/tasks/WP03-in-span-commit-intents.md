---
work_package_id: WP03
title: In-span coordination commits persist their advance intent (#5931)
dependencies: []
requirement_refs:
- FR-006
- SC-002
planning_base_branch: fix/7544-coord-closeout-recovery
merge_target_branch: fix/7544-coord-closeout-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7544-coord-closeout-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7544-coord-closeout-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-recovery-01M75QCY
base_commit: daef3245555590aed89f033bdf67217baf755aa8
created_at: '2026-11-11T16:44:24.849975+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- tests/specify_cli/git/test_safe_commit_in_span_intent_5931.py
- tests/integration/test_consolidate_kill_done_commit_5931.py
- docs/changelog/unreleased/5931-kill-during-done-commits.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/git/ref_advance.py
- src/specify_cli/git/commit_helpers.py
- tests/specify_cli/git/test_safe_commit_in_span_intent_5931.py
- tests/integration/test_consolidate_kill_done_commit_5931.py
- docs/changelog/unreleased/5931-kill-during-done-commits.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 - In-span coordination commits persist their advance intent (#5931)

## Goal

Every `safe_commit` made while a consolidate rollback span reports advance intents
(`reporting_advance_intents`) persists its intent BEFORE the branch moves, by committing through
`safe_commit`'s existing expected-parent mode against the destination's current tip. The run's own
per-WP `status transition` commits are then explained by the record, so a kill in the done-recording
window is undone by `consolidate --abort` instead of being reported "moved by another actor".

Root cause: `research/code-grounding.md` section 2.3. Design: `plan.md` IC-03.

## Subtasks

- **T008** RED (CLI): kill `consolidate` (SIGKILL from a `git` wrapper on `PATH`, matching the
  `commit` whose message contains `status transition WP02`), then run `consolidate --abort`: assert
  no `NOT restored ... moved by another actor` line and that the coordination branch is back at its
  snapshot. This test also depends on WP02's residue fix for the checkout resync: assert only the
  branch restore here; the full recover (abort + re-run) is WP05's. p0_repro marker while red.
- **T009** `git/ref_advance.py`: public `advance_intents_reported() -> bool` (no `specify_cli` import, C-006).
- **T010** `git/commit_helpers.py::safe_commit`: when `expected_parent_sha is None`, no
  `index_deletions`, and `advance_intents_reported()`, read the destination tip and route through
  `_safe_commit_with_expected_parent`. Keep complexity <= 15 (extract a helper).
- **T011** Unit tests: inside a sink, the sink sees `(branch, old, new)` before the ref moves and the
  real index matches HEAD for the committed paths; outside a sink, behaviour and git calls are
  unchanged (NFR-002); a concurrent move between the read and the CAS fails closed. Re-run
  `tests/consolidation/` rollback/intent tests and `tests/consolidation/test_single_rollback_authority.py`.
  Changelog fragment.

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
