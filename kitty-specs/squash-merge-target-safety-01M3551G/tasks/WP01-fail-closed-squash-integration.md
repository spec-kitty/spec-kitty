---
work_package_id: WP01
title: Fail-closed squash integration and forecast parity
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- NFR-005
planning_base_branch: issue-4892-squash-merge-target-safety
merge_target_branch: issue-4892-squash-merge-target-safety
branch_strategy: Planning artifacts for this mission were generated on issue-4892-squash-merge-target-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4892-squash-merge-target-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-squash-merge-target-safety-01M3551G
base_commit: 3b154c875118ae5e92b238944bb72f7fa17197da
created_at: '2026-09-22T18:27:56.010948+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
history:
- '2026-09-22: authored for GitHub issue #4892'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/merge.py
- src/specify_cli/merge/forecast.py
- tests/lanes/test_merge.py
- tests/merge/test_forecast_seam.py
- tests/merge/test_squash_target_newer_planning_3942.py
- docs/guides/how-to/recovery/troubleshoot-merge.md
- docs/changelog/CHANGELOG.md
role: implementer
tags:
- reliability
- git
- merge
tracker_refs:
- github:#4892
---

## Do this first

Load the `python-pedro` agent profile and apply its typed Python, ATDD, and
minimal-surface discipline for the whole package. Work only in the workspace
returned by `spec-kitty implement WP01 --mission squash-merge-target-safety-01M3551G`.

## Objective

Make the default squash mission-to-target branch integration fail closed on
ordinary content conflicts while retaining lossless disjoint merging, registered
artifact merge drivers, target-newer planning reconciliation, and exact dry-run
parity. Close GitHub issue #4892 without changing merge/rebase strategy behavior.

## Context

`src/specify_cli/lanes/merge.py::_merge_branch_into` currently calls
`git merge --squash -X theirs <mission_branch>`. The global option converts
genuine ordinary-source conflicts into success by taking the mission side. The
operation already runs in a detached temporary worktree and advances the target
ref only after commit, so normal Git conflict failure is naturally atomic.

Custom drivers are activated by `_ephemeral_merge_driver_activation`; keep them.
Target-newer PRIMARY planning artifacts are governed by
`target_newer_primary_artifacts` and `_three_way_merge_favouring_target`; keep
that policy path-scoped. `run_dry_run_forecast` currently checks lifecycle state
but never simulates Git branch integration. Its clean JSON key set is frozen.

### T001 — Add red-first execution regressions

- In `tests/lanes/test_merge.py`, create a public-seam regression using
  `integrate_mission_into_target` and `MergeStrategy.SQUASH`.
- Base contains an ordinary source file. Mission and target commit different
  values to the same line.
- Assert the pre-fix behavior is wrong: desired result is non-success, the error
  identifies the conflict path, and source ref, target ref, primary branch name,
  target SHA, and target bytes are unchanged.
- Add the disjoint control: both branches edit different lines in the same file;
  squash succeeds and both values survive.
- Run only the new pins and record that the same-hunk case fails before editing
  product code while the disjoint control passes.

### T002 — Replace blanket preference with path-scoped conflict handling

- Remove `-X theirs` from the squash command. Do not introduce `-X ours`,
  checkout-side wholesale replacement, or a file-extension allowlist.
- Extract a narrow helper for the squash command and deterministic enumeration
  of unmerged repo-relative paths.
- If Git reports conflicts, reconcile only paths selected by the existing
  target-newer PRIMARY planning-artifact authority. Reuse the current three-way
  target-favouring helper; do not duplicate its policy.
- Reinspect the index. Any remaining unmerged path aborts the operation with a
  stable message and leaves the target ref untouched.
- Keep no-op/resume semantics and temporary worktree cleanup unchanged.

### T003 — Add one shared preview primitive

- Add a typed public helper in `lanes/merge.py` that previews mission-to-target
  squash integration by invoking the same isolated squash primitive as execution.
- Preview runs only when both local refs exist and strategy is squash. It always
  discards the temporary worktree and never commits or calls
  `advance_branch_ref`.
- Return a small immutable result with sorted unresolved paths. Do not expose a
  temporary path or raw nondeterministic Git output.
- Preserve the existing ephemeral custom-driver activation and teardown; extend
  its leak tests if required.

### T004 — Surface dry-run conflicts

- In `src/specify_cli/merge/forecast.py`, call the shared preview after the
  existing review-artifact gate and before emitting the ready payload.
- On conflict, emit exit 1 with diagnostic code
  `TARGET_BRANCH_CONTENT_CONFLICT`.
- JSON must include version, mission slug, mission branch, target branch,
  `blocked: true`, sorted conflict paths, and remediation. Human output must be
  concise and actionable.
- If either ref is absent, retain current preview compatibility (notably the
  existing missing-mission-branch tests).
- Do not add keys to the clean successful payload.

### T005 — Add red-first dry-run and safety coverage

- In `tests/merge/test_forecast_seam.py`, add conflict JSON and human-channel
  tests plus a clean-control test.
- Assert exit 1/blocker output for conflict and assert source/target refs and
  tracked bytes are unchanged.
- Assert the clean success key set remains exactly
  `EXPECTED_DRY_RUN_PAYLOAD_KEYS`.
- Prove execution and preview report the same sorted conflict paths.

### T006 — Preserve historical merge policies

- Run the existing custom-driver, information-attributes teardown,
  `test_squash_target_newer_planning_3942.py`, no-op/resume, rebase, and explicit
  merge tests.
- If the normal squash reports an overlapping target-newer planning conflict,
  resolve it only through the existing planning-recency authority. Do not weaken
  the ordinary-source blocker to make the historical tests pass.
- Run a mutation check by temporarily restoring `-X theirs` or bypassing the
  blocker and confirm the new same-hunk tests fail; do not commit the mutant.

### T007 — Document and validate

- Update the merge troubleshooting guide with the new diagnostic and resolution
  flow: update the mission against current target, resolve named files, rerun
  dry-run, then merge.
- Add a concise RC5 changelog entry referencing #4892.
- Run focused pytest, Ruff format/check, targeted mypy, then the repository's
  fast and architecture/contract gates required by the charter.
- Report any pre-existing failure on GitHub and link it before proceeding.

## Definition of done

- Same-hunk ordinary source divergence fails and preserves target SHA/bytes.
- Disjoint same-file edits merge losslessly.
- No blanket `-X theirs` remains in the default squash integration.
- Governed artifact drivers and #3942 planning behavior remain green.
- Dry-run predicts the same blocker and leaves all refs/state untouched.
- Clean dry-run schema stays frozen.
- Explicit merge/rebase strategy tests remain green.
- Documentation, focused checks, and required hard gates pass or have linked
  pre-existing-failure tickets.

## Reviewer guidance

- Reject any implementation that merely changes the preferred side, pre-copies
  all target files, or creates a second planning-path classifier.
- Verify the blocker is raised before commit/ref advancement and before executor
  cleanup/finalization.
- Verify preview and execution call the same squash primitive rather than two
  independently implemented conflict detectors.
- Verify temporary merge-driver activation is fully torn down on both success
  and conflict.
