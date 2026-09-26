---
work_package_id: WP01
title: 'Driver-replay projection attribution (#5038) + #5021-r2 xfail disposition'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: fix/terminus-projection-driver-replay
merge_target_branch: fix/terminus-projection-driver-replay
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-projection-driver-replay. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-projection-driver-replay unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - projection driver-replay attribution
history:
- at: '2026-09-26T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/git_probes.py
- src/specify_cli/merge/bookkeeping_projection.py
- src/specify_cli/merge/executor.py
- tests/terminus/test_repro_5038.py
- tests/merge/test_reconciliation.py
- tests/merge/test_bookkeeping_projection_seam.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5038'
- '#5021'
---

# Work Package Prompt: WP01 — Driver-replay projection attribution (#5038)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the
rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State which initialization/boundaries/directives you applied, then continue.

## Objective

Fix #5038: the DEFAULT-squash projection proof false-REFUSEs a legitimate, lossless union of a
coord-partition bookkeeping path (edited on both the merge target and an approved lane from a shared
baseline). Replace the byte-equality check `coord_bytes == target_bytes` with **driver-replay
attribution**: prove the landed target blob byte-equals the registered `spec-kitty merge-driver-*`
command's OWN deterministic output from `(%O = checkpoint blob, %A = pre-merge-target blob,
%B = coord blob)`. Keep the fail-closed floor: a landed blob that is not the driver's output, or an
unevaluable probe, still REFUSEs. Re-ground `test_5038_p2` onto genuine coord-content loss. Keep the
sibling attribution-axis 3-way residual (#5021-r2) an honest, narrowed strict-xfail.

## Context (read these first)

- `kitty-specs/terminus-projection-driver-replay-01M3EC1K/research.md` — the Phase R findings
  (3 opus lenses, real driver/CLI runs). READ THIS; it is the authority for why driver-replay is the
  only sound fix and why #5021-r2 stays xfail.
- `kitty-specs/terminus-projection-driver-replay-01M3EC1K/data-model.md` — the exact proof contract
  and the four fail-closed invariants (INV-FLOOR-1/2/3, INV-NO-REGRESSION).
- `kitty-specs/terminus-projection-driver-replay-01M3EC1K/quickstart.md` — repro & verify commands.

Grounded seams (post-#5040 base — VERIFY line numbers from the lane worktree before editing):
- `src/specify_cli/merge/executor.py:2307` `_assert_squash_projected_content_landed` — re-derives the
  candidate set from `_post_checkpoint_mission_paths` (FULL set) and demands byte-equality.
- `src/specify_cli/merge/bookkeeping_projection.py:569` `projected_content_matches_target` — the
  `coord_bytes is None or target_bytes != coord_bytes → False` check to replace. Note
  `project_post_checkpoint_commits_to_target` (line ~556) SKIPS a path when the target diverged from
  checkpoint — that asymmetry (assertion checks the full set, projection skips diverged paths) is the
  bug.
- `src/specify_cli/merge/git_probes.py` — probe layer; `_git_show_blob_bytes` in
  `bookkeeping_projection.py` shows the byte-read pattern; `target_baseline_sha`/`pre_mutation_*` on
  the merge run state provide the pre-merge `%A`.
- `src/specify_cli/cli/commands/merge_driver.py:525` `merge_driver_traces` + the driver registry in
  `src/specify_cli/lanes/merge.py` — the deterministic drivers to REPLAY. Reuse; do not fork logic.

## ⚠️ Guardrails (charter-binding)

- **Never green-wash the floor (SO#9 / ADR 2026-07-17-1)**: the re-grounded `test_5038_p2` MUST
  target genuine coord-content loss (a landed blob the driver replay does NOT reproduce), not the old
  lossless union. It stays NON-xfail. All 13 guardian data-loss tests
  (`test_repro_4945/4977/4981/5001/5018/5022`, `test_squash_fails_when_superseded_v1_blob_ships`,
  `test_squash_fails_on_second_parent_smuggled_blob`, `test_squash_unattributed_deletion_fails`,
  `test_squash_authored_deletion_union_across_two_lanes_passes`, `test_squash_passes_clean_no_false_fail`)
  MUST stay GREEN.
- **Format-exclude asymmetry (C-004)**: `executor.py`, `bookkeeping_projection.py`, `git_probes.py`
  are `[tool.ruff.format].exclude` entries — SURGICAL edits only, do NOT reformat. `reconciliation.py`
  is NOT touched by this WP (only its test `test_reconciliation.py` gets a narrowed xfail reason).
- **ATDD red-first (C-011)**: commit the failing/re-grounded tests as the FIRST lane commit; verify
  RED on the merge-base before the fix, GREEN after. Run repros FROM the lane worktree.
- **Quality**: `ruff check`, `mypy --strict`, complexity ≤15, no new `# noqa`/`# type: ignore`. Every
  new helper/branch gets a focused test in the same commit.
- **#5021-r2 is code-out-of-scope** (soundly unfixable); **#4997 (PR #5031) is out** — do not touch.

## Subtasks

### T001 — Registered-driver-replay probe helper
Add a helper (in `git_probes.py`, format-excluded → surgical) that, given a repo-rel path and
`(base_ref, ours_ref, theirs_ref)`, resolves the path's `.gitattributes` `merge=<name>` driver,
materializes the three blobs to temp files, invokes the registered driver (reuse
`cli/commands/merge_driver.py` impls / the `lanes/merge.py` registry), and returns the expected merged
bytes. Raise `GitProbeError` when there is no registered driver for the path, an input blob is
missing, or the driver errors (→ caller REFUSEs). Deterministic/idempotent.

### T002 — Rewire the projection proof to driver-replay attribution
In `projected_content_matches_target` (and the `_assert_squash_projected_content_landed` call-site as
needed): for each projected path, keep the existing PASS when the target did NOT diverge from
checkpoint (`ours == base`; `coord == target` still holds — FR-004, no regression); otherwise
attribute via T001's probe — PASS iff `landed == replay`, REFUSE fail-closed on any unevaluable probe
(FR-002/FR-003). Preserve exit/rollback semantics of the existing assertion.

### T003 — Flip `test_5038_p1`
Remove the strict-xfail from `test_5038_p1_clean_single_lane_squash_must_not_false_refuse`. Verify RED
on the merge-base (via `git stash`/base checkout or the pre-fix state) and GREEN on the lane head,
through the real `spec-kitty merge` CLI.

### T004 — Re-ground `test_5038_p2` onto genuine loss
Rewrite `test_5038_p2_genuine_projection_failure_still_refuses` so its scenario is a landed blob the
driver replay does NOT reproduce (genuine coord-content loss/tampering) — the projection REFUSE must
still fire. Keep it NON-xfail (it is the floor). Update the module docstring to reflect the fixed
disposition (no longer "kept honest xfail").

### T005 — Probe unit tests
Add focused unit tests (in `tests/merge/test_bookkeeping_projection_seam.py`): driver-governed PASS on
a lossless union; REFUSE on a tampered/dropped-content blob; REFUSE on no-driver / missing-blob /
probe-error. Complexity ≤15 per function.

### T006 — Narrow #5021-r2 xfail reason
In `tests/merge/test_reconciliation.py`, narrow the `test_squash_three_way_merge_resolution_is_unattributable`
xfail reason to name the distinct root (stock-git conflict + manual resolution, NOT the deterministic
union driver now handled by #5038) and reference the dedicated follow-up issue. Keep `xfail(strict=True)`.

### T007 — CHANGELOG entry
Add a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry: bold impact-first lead + `(#5038)` +
before→after; note the #5021-r2 honest-xfail disposition.

## Branch Strategy

Planning base: `fix/terminus-projection-driver-replay`. This WP is materialized in its computed lane
worktree from `lanes.json` during `/spec-kitty.implement`; do not reconstruct the path by hand.
Completed changes merge back into `fix/terminus-projection-driver-replay`; the mission PR targets
`main` upstream. The human/operator performs the mainline merge.

## Definition of Done

- [ ] `test_5038_p1` PASSES via the real CLI (was strict-xfail/RED on base).
- [ ] `test_5038_p2` (re-grounded) still REFUSEs on genuine loss; NON-xfail.
- [ ] All 13 guardian data-loss tests GREEN; `tests/merge/ tests/terminus/ tests/coordination/` green modulo the narrowed #5021-r2 xfail.
- [ ] `test_squash_three_way_merge_resolution_is_unattributable` remains strict-xfail with narrowed reason.
- [ ] Probe helper has focused unit tests; complexity ≤15; ruff/mypy clean; no new suppressions.
- [ ] No reformat of the three format-excluded files.
- [ ] CHANGELOG `[Unreleased]` entry added.
- [ ] Foreign-coverage baseline recaptured to the MEASURED value only if a new real-CLI repro was added.

## Reviewer Guidance (opus)

Adversarial data-loss lens: prove the re-grounded `test_5038_p2` is genuine loss, not a disguised
lossless union (green-wash check). Confirm `%A` is the pre-squash target blob (not tautological).
Confirm the fail-closed branches (no-driver / missing-blob / probe-error → REFUSE) are exercised.
Confirm the product-content attribution axis and the 13 guardians are untouched/green.
