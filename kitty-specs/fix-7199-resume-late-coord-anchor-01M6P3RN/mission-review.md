# Mission review — #7199 (post-consolidation, pre-PR)

Scope: the integrated diff on `issue-7199-resume-late-coord-anchor` after `consolidate`
(`git diff origin/main..HEAD -- src/ tests/ docs/`). Reviewed against `spec.md` FR/SC rows and
`plan.md` IC-01/IC-02.

## Fidelity

| Requirement | Evidence |
|---|---|
| FR-001 | `phase_teardown._land_late_coordination_commits`: the advance is unconditional on run kind and still gated by `projected_tip` + live-ref equality. `test_resume_lands_a_coordination_commit_made_after_its_own_capture` drives `_teardown_coordination_triple` to completion (branch deleted at the proven tip, record committed on the target). Red at base with the gate's `compare-and-swap failed`. |
| FR-002 | `test_resume_does_not_approve_a_tip_that_moved_during_the_projection` injects a foreign commit during the projection on the same fixture: `ProjectionTeardownAbort`, anchor unmoved, branch kept. |
| FR-003 | `test_a_clean_first_run_projects_nothing`, `test_resume_with_nothing_landed_late_commits_nothing` unchanged and green. |
| FR-004 | `test_resume_with_an_unreadable_window_refuses_and_keeps_the_branch`, `test_first_run_refuses_rather_than_skips_a_window_it_cannot_read`, `test_resume_refuses_a_window_that_deletes_a_checkpoint_present_record[gate-matrix|tracer]` unchanged and green. |
| FR-005 | `docs/guides/how-to/recovery/recover-from-interrupted-merge.md` section `### What a run lands before it tears down`; field comment in `run_state.py`; docstrings in `phase_teardown.py`. |
| C-001 | The diff reuses `_land_late_coordination_commits`, `assert_late_window_landed` and the existing field; no new selector/refusal/field. |
| C-002 | `assert_late_window_landed`, `ProjectionTeardownGate`, `_delete_mission_branch`, `_refuse_unbuildable_late_window` and the unreadable-ref refusal are byte-unchanged. |
| C-003 | One behavioural line (`if not run.is_resume and projected_tip ...` → `if projected_tip ...`), plus prose. `git diff origin/main..HEAD -- tests/` shows 0 deleted lines. |
| NFR-001 | No CLI flag, config key, exit code or error code added; grep of the diff for `typer.Option|EXIT_CODE|error_code` finds none. |
| SC-001 | Red→green proven (see above). |
| SC-002 | 771 passed `tests/coordination`; 416 passed `tests/terminus` + two architectural gates; 37 passed in each of the two directly covering files. No assertion edited to pass. |
| SC-003 | Anchor equals the projected tip in the landing case; unchanged in the moved-tip case and in both no-op cases. |

## Drift / risk

- No behaviour outside the anchor moved. The widened surface for assertion-exempt files
  (status byte-sets, `meta.json`) is #7198's, named in the PR `## Deferred`.
- The recovery guide heading was renamed; the generated docs index row is left to the
  `ci/regen-docs-index` bot (`check_docs_freshness --ci`: errors=0).
- The concurrency window cannot be driven deterministically through the real CLI; the
  reproduction is in-process and the real-CLI resume case is the unchanged positive control
  (`tests/consolidation/test_late_teardown_projection.py`, 18 passed).

## Verdict

Ready for PR review. No unresolved finding above `low`; the two analysis-report findings (C1
coverage placement, T1 docs-index row) are dispositioned there and in the PR body.
