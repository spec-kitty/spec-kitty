---
work_package_id: WP01
title: Accept commits its record through the placement seam (#7550)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- SC-001
planning_base_branch: fix/7544-coord-closeout-recovery
merge_target_branch: fix/7544-coord-closeout-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7544-coord-closeout-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7544-coord-closeout-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-closeout-recovery-01M75QCY
base_commit: d8479e89066d1b5ba8142a9be1cf1bbc5d48b9cf
created_at: '2026-11-11T16:42:41.929185+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/integration/test_accept_record_commit_coord_7550.py
- tests/specify_cli/acceptance/test_accept_record_commit_unit_7550.py
- docs/changelog/unreleased/7550-accept-record-commit-coord.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/acceptance/__init__.py
- tests/integration/test_accept_record_commit_coord_7550.py
- tests/specify_cli/acceptance/test_accept_record_commit_unit_7550.py
- docs/changelog/unreleased/7550-accept-record-commit-coord.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 - Accept commits its record through the placement seam (#7550)

## Goal

`spec-kitty accept` on a settled `lanes_with_coord` Mission (root checkout on the unprotected
target) commits its acceptance record on the Mission branch through the commit router, records
`accepted_from_commit` = the tip of the branch the record is written on, and turns any record-commit
failure into the named refusal `ACCEPT_RECORD_COMMIT_FAILED` (no traceback).

Root cause and line refs: `research/code-grounding.md` section 2.1. Design: `plan.md` IC-01.

## Subtasks

- **T001** RED: integration test through `spec-kitty accept` on the fixture (after recording the
  acceptance-matrix verdicts with `agent mission acceptance-verdict`): asserts exit 0, a commit on
  the Mission branch touching the Mission's `meta.json`, a clean coordination worktree, and
  `accepted_from_commit` equal to the Mission branch tip before accept. Red on the base with the
  `.worktrees` gitignore traceback. p0_repro marker while red.
- **T002** Fix: `_commit_acceptance_meta` always commits through `_commit_acceptance_meta_via_router`
  (delete the raw `run_git(["add", ...], cwd=repo_root)` path). `parent_commit` is `rev-parse HEAD`
  run in `summary.feature_dir`. Keep the protected-primary behaviour unchanged.
- **T003** Named refusal: router non-committed status and git/router exceptions become
  `AcceptanceError` carrying `ACCEPT_RECORD_COMMIT_FAILED` (message names the code and the remedy);
  verify the CLI renders it without a traceback (unit test forcing the router to fail).
- **T004** Keep `status_phase` (design decision DD-1); update the existing acceptance unit tests that
  pinned the raw path (judge each: stale -> re-pin). Changelog fragment.

## Tests to run

`tests/specify_cli/acceptance/`, `tests/specify_cli/cli/commands/test_accept_guidance_liveness.py`,
`tests/integration/test_protected_primary_spec_commit.py`, the new tests,
`tests/architectural/test_commit_scope_owner.py`.

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
