# Discovery findings — #7199 resume late-coordination anchor

## Grounding on `main` @ `b4d1e918e2` (2026-11-05)

- The defect is real on current `main` and is the `--resume` half of the seam #6871/PR #7124
  just fixed for the first run. `_land_late_coordination_commits`
  (`src/specify_cli/consolidation/phase_teardown.py`) ends with

  ```python
  if not run.is_resume and projected_tip and _resolve_ref_sha(run.main_repo, coord_ref) == projected_tip:
      run.coord_tip_after_projection = projected_tip
  ```

  so only a first run records the proven tip as the one teardown approved.
- `_teardown_coord_worktree` builds the projection teardown gate with
  `expected_coord_sha = run.coord_tip_after_projection or checkpoint.sha`, and `_delete_mission_branch`
  compare-and-swaps the same value. A resume that lands a commit made *after* its own capture
  therefore refuses at the gate: "the coordination tip moved since projection captured its
  window (compare-and-swap failed)".
- Where the resume's capture comes from: `_capture_coord_checkpoint` at claim time
  (`phase_claim._capture_reconciliation_claim`) and, when the resume runs every phase,
  `phase_bookkeeping._phase_record_done_and_project` (the last line captures the live tip).
  A resume that short-circuits the phase list via `_resume_reconciliation_already_passed`
  (#5021 residual 1) never captures it at all and falls back to the claim-time checkpoint.
- `_late_window_base` gives a resume `state.pre_mutation_coord_sha`, i.e. a base at or before the
  capture, so the resume window always covers at least the first-run window. This is why the
  issue's suggested fix is sound: the advance is justified by the same assertion
  (`assert_late_window_landed`) on a superset window.
- The advance is guarded by `_resolve_ref_sha(...) == projected_tip`, a compare-and-swap on the
  tip the assertion was made over. A commit landing during the projection leaves the old anchor
  and the gate refuses (fail-closed). This leg must be preserved verbatim.

## Prior art / related

- PR #7124 (`[#6871] consolidate: a first run lands the coordination commit it never received`)
  landed 2026-11-05 and deferred this exact item as reviewer finding B5, because it changes
  `--resume` behaviour.
- #7198 (open) changes what `assert_late_window_landed` proves (status-only / `meta.json`-only
  late commits) on both run kinds; it touches `bookkeeping_projection.py`, not the anchor
  advance. #7209 (open) touches `entry_preflight.py`. Neither conflicts with this change; the
  PR body names the shared seam.
- #7121 (open) covers the anchorless first run, which this mission does not change.

## Decisions

- **D1 — Drop the run-kind guard; do not add a second path.** The issue's own suggested fix and
  the #7124 machinery both point at one condition. A resume-only helper or a second capture
  would duplicate the window selector.
- **D2 — Keep the compare-and-swap.** The advance stays `projected_tip and live ref == projected_tip`.
  This is the only thing that makes the advance "the tip the assertion covered" rather than
  "whatever was last read".
- **D3 — Red-first at the teardown entry point.** The reproduction needs a coordination commit
  that lands after the run's own capture and before its window read — a concurrency window that
  the real-CLI resume test cannot produce deterministically. The red test therefore drives
  `_teardown_coordination_triple` on a real git fixture with the commit injected between the
  capture and the teardown, exactly the shape #7124 used for its first-run twin
  (`tests/coordination/test_projection_teardown.py`). The real-CLI resume test in
  `tests/consolidation/test_late_teardown_projection.py` stays as the end-to-end positive
  control and is strengthened where it can observe the change.
- **D4 — No product behaviour change outside the anchor.** No CLI flag, config key, exit code,
  error code or refusal text changes. Docs and the field comment that describe the anchor as
  "first run only" are corrected.

## Open questions

- None that need an operator. The one judgement call (does a resume's wider window justify the
  advance?) is answered by the window being a superset of the first-run window plus the same
  post-projection assertion.
