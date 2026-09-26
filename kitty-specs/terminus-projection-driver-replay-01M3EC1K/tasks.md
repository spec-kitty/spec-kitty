# Tasks: Terminus Projection Driver-Replay Attribution

**Mission**: terminus-projection-driver-replay-01M3EC1K
**Planning base branch**: `fix/terminus-projection-driver-replay`
**Merge target**: `main` (upstream `spec-kitty/spec-kitty`)

One cohesive fix (driver-replay attribution for the squash projection proof) plus its test
re-grounding and the sibling #5021-r2 residual disposition. Single work package — the pieces share
the merge/ domain and one ATDD red→green story; splitting a 2-subtask doc slice into its own lane
would be below the minimum WP size.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add a registered-driver-replay probe helper (replay `merge=<name>` driver on base/ours/theirs blobs), fail-closed on unevaluable | WP01 | |
| T002 | Rewire projection proof to driver-replay attribution; preserve non-diverged PASS; fail-closed | WP01 | |
| T003 | Flip `test_5038_p1` (remove strict-xfail): RED on base, GREEN after fix via real CLI | WP01 | |
| T004 | Re-ground `test_5038_p2` onto genuine coord-content loss (still REFUSE; stays the floor) | WP01 | |
| T005 | Add focused probe unit tests (new-code coverage; complexity ≤15) | WP01 | |
| T006 | Narrow `test_squash_three_way_merge_resolution_is_unattributable` xfail reason (#5021-r2) | WP01 | |
| T007 | CHANGELOG `[Unreleased]` entry (#5038 fix + #5021-r2 disposition) | WP01 | |

## WP01 — Driver-replay projection attribution + residual disposition

**Goal**: Replace the squash projection proof's `coord_bytes == target_bytes` byte-check with a
driver-replay attribution proof so a legitimate lossless union PASSes (#5038) while genuine
non-landing/tampering still REFUSEs; re-ground the P2 floor; keep #5021-r2 an honest, narrowed xfail;
record the CHANGELOG entry.

**Priority**: P1 (shipped merge-integrity defect)

**Independent test**: `tests/terminus/test_repro_5038.py::test_5038_p1_...` flips strict-xfail(RED)→PASS
through the real `spec-kitty merge` CLI; `test_5038_p2_...` (re-grounded) still REFUSEs; the 13
guardian data-loss tests stay green.

**Included subtasks**: T001, T002, T003, T004, T005, T006, T007

**Implementation sketch**:
1. T001 — driver-replay probe helper in `git_probes.py` (format-excluded → surgical edits only): given
   a repo-rel path and `(base_ref, ours_ref, theirs_ref)`, resolve the path's `.gitattributes`
   `merge=<name>` driver, materialize the three blobs, invoke the registered driver, and return the
   expected bytes. Raise `GitProbeError` (→ REFUSE) when there is no registered driver, an input blob
   is missing, or the driver errors. Reuse the existing driver impls in `cli/commands/merge_driver.py`
   / the registry in `lanes/merge.py`; do NOT fork merge logic.
2. T002 — in `bookkeeping_projection.py::projected_content_matches_target` (and the
   `executor.py::_assert_squash_projected_content_landed` call-site as needed), for each projected
   path: keep the existing PASS when `ours == base` (non-diverged; `coord == target` still holds);
   otherwise attribute via the driver-replay probe (PASS iff `landed == replay`); REFUSE fail-closed
   on any unevaluable probe. Both files are format-excluded → surgical edits, no reformat.
3. T003 — remove the strict-xfail on `test_5038_p1`; verify RED on the merge-base and GREEN on the
   lane head via the real CLI (run from the lane worktree).
4. T004 — re-ground `test_5038_p2` onto a genuinely-lossy scenario (a landed blob the driver replay
   does NOT reproduce — real coord-content loss/tampering), asserting the projection REFUSE still
   fires. Keep it NON-xfail (it is the floor). This is the operator-sanctioned re-grounding
   (`DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`), not a green-wash.
5. T005 — focused unit tests for the probe helper (driver-governed PASS on a lossless union; REFUSE on
   a tampered/dropped-content blob; REFUSE on no-driver / missing-blob / probe-error). Keep each
   function complexity ≤15.
6. T006 — narrow the `test_squash_three_way_merge_resolution_is_unattributable` xfail reason to name
   the distinct root (stock-git conflict + manual resolution, NOT the deterministic union driver) and
   reference the dedicated follow-up issue for #5021-r2.
7. T007 — `docs/changelog/CHANGELOG.md` `[Unreleased]` entry: bold impact-first lead + `(#5038)` +
   before→after; note the #5021-r2 honest-xfail disposition.

**Dependencies**: none.

**Risks**:
- **Green-wash hazard (highest)**: the re-grounded `test_5038_p2` must target genuine loss, not the
  lossless union. Adversarial-lens it post-tasks and pre-merge.
- **`%A` correctness**: the replay's "ours" must be the target blob BEFORE the squash
  (`target_baseline_sha`/`pre_mutation_*`), not the post-squash target — else the replay is
  tautological. Confirm the exact run-state field via the brownfield scout.
- **Format-exclude asymmetry**: do not reformat `executor.py`/`bookkeeping_projection.py`/`git_probes.py`.
- **Foreign-coverage baseline**: recapture only if a new real-CLI repro is added under `tests/terminus/`.

**Estimated prompt size**: ~350 lines.

## Out of scope

- #5021 residual-2 code fix (soundly unfixable — honest xfail only).
- #4997 (staged-deletion `LOCAL_CHANGES` window, PR #5031) — distinct class, do not touch.
